# .. title:: Basic rubric usage
# This vignette includes a rubric and uses a "grader function".
# Rubrics are defined with a prompt template and a map of string outputs to numeric choice scores.
import flexeval
from flexeval.metrics import access
from flexeval.schema import (
    Config,
    DependsOnItem,
    Eval,
    EvalRun,
    FileDataSource,
    FunctionItem,
    GraderLlm,
    Metrics,
    Rubric,
    RubricItem,
    RubricsCollection,
)

data_sources = [FileDataSource(path="vignettes/conversations.jsonl")]
rubric = Rubric(
    prompt="Answer YES if the response is helpful, NO otherwise.",
    choice_scores={"YES": 1, "NO": 2},
)
# using a placeholder grader, but you can use any supported completion function
grader_llm = GraderLlm(function_name="echo_completion", kwargs={"response": "YES"})
is_assistant_dependency = DependsOnItem(
    name="is_role", kwargs={"role": "assistant"}, metric_min_value=1
)
eval = Eval(
    name="basic_eval",
    metrics=Metrics(
        function=[
            FunctionItem(name="is_role", kwargs={"role": "assistant"}),
            FunctionItem(
                name="flesch_reading_ease",
                depends_on=[is_assistant_dependency],
            ),
        ],
        rubric=[RubricItem(name="is_helpful", depends_on=[is_assistant_dependency])],
    ),
    grader_llm=grader_llm,
)
config = Config(clear_tables=True, logs_path="tmp")
eval_run = EvalRun(
    data_sources=data_sources,
    database_path="eval_results.db",
    eval=eval,
    config=config,
    rubric_paths=[RubricsCollection(rubrics={"is_helpful": rubric})],
)
flexeval.run(eval_run)
for metric in access.get_all_metrics():
    print(
        f"{metric['thread']} {metric['turn']} {metric['evaluation_name']} {metric['metric_value']:.1f}"
    )
