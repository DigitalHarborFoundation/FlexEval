# `context_only` Feature

## What it does

For function metrics, `context_only=True` means: instead of passing the current object's content to the metric function, pass only the *preceding context* (previous turns/messages). This enables metrics like "was the conversation flagged before this point?" or "what's the reading ease of everything before this turn?"

The implementation in `function_types.py` is complete — it calls `get_context()` instead of `get_content()` on Thread/Turn/Message objects when `context_only=True`. For rubric metrics, `context_only` is irrelevant — rubrics use a `{context}` template variable instead.

## Current status: broken (silently ignored)

The full data flow is broken at the Pydantic schema entry point:

1. **YAML** → `context_only: true` on a FunctionItem
2. **Pydantic** → `FunctionItem` inherits from `MetricItem`, which has no `context_only` field. `BaseModel` defaults to `extra='ignore'` → **silently dropped**
3. **dependency_graph.py** → `item.model_dump()` never includes `context_only`
4. **compute_metrics.py** → `compute_metric()` receives `context_only=None` (default param)
5. **function_types.py** → `get_function_input()` treats `None` as falsy → always uses current content, never context
6. **save.py** → `metric.get("context_only", False)` → writes `False` to `Metric.create(context_only=False)`
7. **Metric model** → `context_only` column is **commented out** (`metric.py:47`)
8. **Peewee** → silently ignores the unknown `context_only` kwarg in `create()`

## Plan to restore

### 1. `src/flexeval/schema/eval_schema.py` — Add field to MetricItem

Add `context_only` to `MetricItem` (inherited by both `FunctionItem` and `RubricItem`):

```python
class MetricItem(BaseModel):
    ...
    context_only: bool = Field(
        False,
        description="If true, only the context (preceding messages) will be evaluated, not the current object.",
    )
```

This ensures `model_dump()` in `dependency_graph.py` includes it, and it flows through `compute_metrics.py` to `function_types.py`.

### 2. `src/flexeval/classes/metric.py` — Uncomment column

Uncomment the `context_only` field (currently lines 40-47):

```python
context_only = pw.BooleanField(default=False)
```

This allows `save.py:36` (`context_only=metric.get("context_only", False)`) to persist correctly.

### 3. `tests/integration/functional_tests.py` — Remove expectedFailure

Remove `@unittest.expectedFailure` from `test_reading_ease_levels_by_level` since the column will exist again.

## Verification

1. `uv run python -m unittest discover -s tests.unit` — all pass
2. `uv run python -m unittest tests.integration.functional_tests.TestListStringInputFunctionMetrics` — `test_reading_ease_levels_by_level` passes (no longer expectedFailure)
3. Verify `context_only: true` in YAML actually affects metric computation (e.g. via the existing `test_function_types.py` tests)


# Investigation: Should we support the `context_only` feature?

## Context

`context_only` is a flag on function metrics that, when `True`, passes the preceding conversation context to the metric function instead of the current object's content. It's been silently broken for some time: the Pydantic schema field was never added, the DB column is commented out, and the integration test is marked `@unittest.expectedFailure`.

## How it works (when functional)

In `src/flexeval/function_types.py:101-162`, `get_function_input()` checks `context_only`:
- For functions accepting `list` (lines 139-144): calls `input_object.get_context()` instead of `get_content()`
- For functions accepting `str` (lines 145-155): joins context messages into a string instead of content

This lets a generic function like `flesch_reading_ease(turn: str)` be reused on the preceding context without modification.

## Where it's broken (8 points of failure)

1. **Schema** (`eval_schema.py`): `MetricItem` has no `context_only` field → silently dropped during YAML parsing
2. **Dependency graph** (`dependency_graph.py`): `model_dump()` never includes it
3. **Compute** (`compute_metrics.py:486`): receives `context_only=None` (default)
4. **Function types** (`function_types.py`): `None` is falsy → always uses content
5. **Save** (`metrics/save.py:36`): attempts to persist, but...
6. **DB model** (`classes/metric.py:47`): column is commented out
7. **Peewee**: silently ignores the unknown kwarg
8. **Tests** (`functional_tests.py:1040`): marked `@unittest.expectedFailure`

## Can `depends_on` + `relative_object_position` replace it?

**No.** They solve different problems:
- `depends_on` + `relative_object_position`: "only run this metric if a condition was met on a *different* object (e.g., previous turn)"
- `context_only`: "run this metric on the current object, but pass it the *preceding content* instead of its own content"

However, the question isn't whether the dependency system replaces it — it's whether `context_only` is the right abstraction for this need.

## Recommendation: Remove `context_only`

### Why remove

1. **No one has noticed it's broken.** The feature has been silently non-functional with no complaints, suggesting very low demand. YAML configs referencing it (`tests/integration/evals.yaml`, `src/flexeval/configuration/evals.yaml`) are producing wrong results silently.

2. **Implicit magic is confusing.** The same function (`flesch_reading_ease`) produces fundamentally different results depending on a flag invisible in the function signature. This makes debugging hard — you can't tell what a metric measured by looking at its name and source.

3. **Rubrics already have the right pattern.** For rubrics, `{context}` vs `{content}` template variables make the distinction explicit and readable. The function metric system should follow a similarly explicit approach.

4. **The alternative is trivial.** A user who wants `flesch_reading_ease` of the preceding context writes:
   ```python
   def flesch_reading_ease_of_context(turn: Turn) -> float:
       context = turn.get_context()
       text = "\n".join([item.get("content", "") for item in context])
       return textstat.flesch_reading_ease(text)
   ```
   This is ~5 lines, fully explicit, and needs no framework support.

5. **It complicates the dependency graph.** `context_only` appears in the dependency matching conditionals (`dependency_graph.py:148`), adding complexity for a feature that doesn't work.

6. **Storing it as a DB column is wrong.** `context_only` describes the metric *definition*, not the metric *result*. It belongs in the eval config, not in every row of the metrics table. (The `source` and `kwargs` columns already capture this if the user writes an explicit function.)

### What removing looks like

1. **Delete all `context_only` references** from:
   - `src/flexeval/function_types.py` — remove the parameter from `get_function_input()`, always use `get_content()`
   - `src/flexeval/compute_metrics.py` — remove `context_only` parameter from `compute_metric()` and `compute_function_metric()`
   - `src/flexeval/dependency_graph.py` — remove from conditionals list
   - `src/flexeval/metrics/save.py` — remove from `Metric.create()` call
   - `src/flexeval/classes/metric.py` — remove commented-out column and comments
   - `tests/unit/test_function_types.py` — remove `context_only` parameter from test calls
   - `tests/integration/functional_tests.py` — remove the `@expectedFailure` test entirely
   - `tests/integration/evals.yaml` — remove `context_only` keys
   - `src/flexeval/configuration/evals.yaml` — remove `context_only` keys
   - `CONTEXT_ONLY_FEATURE.md` — delete the file

2. **Add a Pydantic validation error** (optional, nice-to-have): If someone passes `context_only` in YAML, raise a clear error instead of silently ignoring it. This could be done by setting `model_config = ConfigDict(extra='forbid')` on `MetricItem`, or by adding a custom validator.

3. **Document the explicit alternative**: In a docstring or vignette, show how to write a function metric that operates on context by accepting a Turn/Thread object and calling `get_context()`.

### What fixing would look like (if you disagree)

If you'd prefer to restore the feature, the fix is small (as documented in CONTEXT_ONLY_FEATURE.md):
1. Add `context_only: bool = Field(False, ...)` to `MetricItem` in `eval_schema.py`
2. Uncomment the column in `metric.py`
3. Remove `@expectedFailure` from the integration test

## Verification

After removal:
- `uv run python -m unittest discover -s tests.unit` — all pass
- `uv run ruff check src/` — no lint errors
- Grep confirms no remaining `context_only` references outside of git history
