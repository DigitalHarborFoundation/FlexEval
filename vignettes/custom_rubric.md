# Custom rubrics in FlexEval

In addition to the built-in rubrics, you can write your own rubrics.

The `eval_run.yaml` schema used in {ref}`basic_cli` shows an example {class}`~flexeval.schema.evalrun_schema.EvalRun` using a custom rubric.

The easiest way to provide custom rubrics is in a YAML file; here's `vignettes/custom_rubrics.yaml`:

```{literalinclude} ../../../vignettes/custom_rubrics.yaml
:language: yaml
:linenos:

```

You then need to specify the path to that YAML file in your {class}`~flexeval.schema.evalrun_schema.EvalRun` configuration:

```yaml
rubric_paths:
 - vignettes/custom_rubrics.yaml
```

Then, you can use those custom rubrics in your {attr}`~flexeval.schema.eval_schema.Metrics.rubrics` definition.

## Writing rubrics

Rubrics consist of a `prompt` and a set of `choice_scores`.
 - `choice_scores` are the LLM outputs that will result in a numeric score.
 - `prompt` is a template that will be formatted and passed to the rubric LLM (see Eval) for scoring.

See the {ref}`rubric_guide` for additional information on writing rubrics.

### Supported template parameters

The following parameters can be used and replaced in a rubric:

 - context
 - content

In the future, we hope to support templated inputs from other metrics.
