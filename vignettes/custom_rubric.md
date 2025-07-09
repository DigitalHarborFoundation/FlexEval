# Custom rubrics in FlexEval

In addition to the built-in rubrics, you can write your own rubrics.

[`eval_run.yaml`](eval_run.yaml) shows an example Eval Run using a custom rubric.

The easiest way to provide custom rubrics is in a YAML file; [`eval_run.yaml`](custom_rubrics.yaml) is an example.

You then need to specify the path to that YAML file in your Eval Run configuration:

```yaml
rubric_paths:
 - vignettes/custom_rubrics.yaml
```

Then, you can use custom rubrics

## Writing rubrics

Rubrics consist of a `prompt` and a set of `choice_scores`.
 - `choice_scores` are the LLM outputs that will result in a numeric score.
 - `prompt` is a template that will be formatted and passed to the rubric LLM (see Eval) for scoring.

See the Rubric Guide for additional information on writing rubrics.

### Supported template parameters

The following parameters can be used and replaced in a rubric:

 - context
 - content

In the future, we hope to support templated inputs from other metrics.
