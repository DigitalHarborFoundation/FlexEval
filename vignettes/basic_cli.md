# Basic CLI usage

All of FlexEval's features can be accessed using YAML configuration files.

Running an eval is as simple as pointing to that configuration file and using the {func}`~flexeval.cli.run` command:

```bash
flexeval run vignettes/eval_run.yaml
```

The file `vignettes/eval_run.yaml` demonstrates a complete configuration using the {class}`~flexeval.schema.evalrun_schema.EvalRun` schema.

```{literalinclude} ../../../vignettes/eval_run.yaml
:language: yaml
:linenos:

```

Use the {func}`~flexeval.cli.summarize_metrics` command to print a result summary:

```bash
python -m flexeval summarize-metrics vignettes/eval_run.yaml
```

See {ref}`metric_analysis` for a more in-depth vignette analyzing FlexEval outputs.
