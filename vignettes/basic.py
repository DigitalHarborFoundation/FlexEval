import flexeval
from flexeval.metrics import access
from flexeval.schema import Config, Eval, EvalRun, FileDataSource, FunctionItem, Metrics

data_sources = [FileDataSource(path="vignettes/conversations.jsonl")]
eval = Eval(metrics=Metrics(function=[FunctionItem(name="index_in_thread")]))
config = Config(clear_tables=True)
eval_run = EvalRun(
    data_sources=data_sources,
    database_path="eval_results.db",
    eval=eval,
    config=config,
)
flexeval.run(eval_run)
for metric in access.get_all_metrics():
    print(
        f"{metric['thread']} {metric['turn']} {metric['metric_name']} {metric['metric_value']}"
    )
