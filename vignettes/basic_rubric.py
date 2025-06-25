import flexeval
from flexeval.schema import (
    Eval,
    EvalRun,
    FileDataSource,
    Metrics,
    FunctionItem,
    RubricItem,
    DependsOnItem,
    Config,
)
from flexeval.metrics import access

data_sources = [FileDataSource(path="vignettes/conversations.jsonl")]
rubric = None
eval = Eval(
    name="basic_eval",
    metrics=Metrics(
        function=[
            FunctionItem(name="is_role", kwargs={"role": "assistant"}),
            FunctionItem(
                name="flesch_reading_ease",
                depends_on=[
                    DependsOnItem(name="is_role", kwargs={"role": "assistant"})
                ],
            ),
        ]
    ),
)
config = Config(clear_tables=True, logs_path="tmp")
eval_run = EvalRun(
    data_sources=data_sources,
    database_path="eval_results.db",
    eval=eval,
    config=config,
)
flexeval.run(eval_run)
for metric in access.get_all_metrics(eval_run.database_path):
    print(
        f"{metric['thread']} {metric['turn']} {metric['metric_name']} {metric['metric_value']}"
    )
