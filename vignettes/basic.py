import flexeval
from flexeval.schema import Eval, EvalRun, FileDataSource, Metrics, FunctionItem, Config
from flexeval.metrics import access

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
for metric in access.get_all_metrics(eval_run.database_path):
    print(
        f"{metric['evalsetrun']} {metric['dataset']} {metric['thread']} {metric['turn']} {metric['metric_name']} {metric['metric_value']}"
    )
