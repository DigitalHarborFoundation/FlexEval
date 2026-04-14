# .. title:: Multiple configurations
# If you name a dataset, even an in-memory IterableDataSource, you can reuse it in multiple runs with different configurations.
import flexeval
from flexeval.metrics import access
from flexeval.schema import (
    Config,
    Eval,
    EvalRun,
    FunctionItem,
    IterableDataSource,
    Metrics,
)

# You can load conversations directly from Python using IterableDataSource
# Each thread is a dict with an "input" key containing a list of messages
conversations = [
    {
        "input": [
            {"role": "user", "content": "What is 2+2?"},
            {"role": "assistant", "content": "The answer is 4."},
            {"role": "user", "content": "Thanks!"},
            {
                "role": "assistant",
                "content": "You're welcome! Let me know if you have more questions.",
            },
        ]
    },
    {
        "input": [
            {"role": "user", "content": "Can you help me write a regex?"},
            {
                "role": "assistant",
                "content": "Sure! What pattern do you need to match?",
            },
        ]
    },
]

# Name the data source so it can be reused across eval runs.
# The data is loaded into the database on the first run and reused on the second.
data_sources = [
    IterableDataSource(name="vignette_conversations", contents=conversations)
]

# --- Config 1: applying the index_in_thread function to ---
# Computes the position of each turn within a thread.
eval_run_1 = EvalRun(
    data_sources=data_sources,
    database_path="eval_results.db",
    eval=Eval(metrics=Metrics(function=[FunctionItem(name="index_in_thread")])),
    config=Config(clear_tables=True),
)
flexeval.run(eval_run_1)
print("=== Run 1: index_in_thread ===")
for metric in access.get_all_metrics():
    print(
        f"  thread={metric['thread']} turn={metric['turn']}"
        f" {metric['metric_name']}={metric['metric_value']}"
    )

# --- Run 2: message_matches_regex ---
# Counts question marks in each message.
# The named dataset "demo_conversations" is reused from Run 1.
# Note that you could use a flexeval.schema.NamedDataSource instead if you wanted.
eval_run_2 = EvalRun(
    data_sources=data_sources,
    database_path="eval_results.db",
    eval=Eval(
        metrics=Metrics(
            function=[
                FunctionItem(
                    name="message_matches_regex",
                    metric_level="Message",
                    kwargs={"expression": r"\?"},
                )
            ]
        )
    ),
    config=Config(clear_tables=False),
)
flexeval.run(eval_run_2)
print("\n=== Run 2: message_matches_regex (question marks) ===")
for metric in access.get_all_metrics():
    if metric["evaluation_name"] == "message_matches_regex":
        print(
            f"  thread={metric['thread']} message={metric['message']}"
            f" {metric['metric_name']}={metric['metric_value']}"
        )
