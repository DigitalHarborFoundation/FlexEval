# LEVI LLM Evals

Author: Thomas Christie

## Development

Python version 3.11.

To use the pre-commit configs, install them:

```bash
pip install pre-commit # if needed
pre-commit autoupdate
pre-commit install
```

## Overview

The OpenAI Evals package is used to test the outputs of LLMs. Evals is intended to be used to evaluate the behavior of LLMs or LLM systems. A typical evaluation consists of:

- text input, which usually consists of a system prompt and a "user" prompt
- an "ideal" output
- an LLM to be tested

The LLM is fed the text input, produces a response (called a `completion`), and the output is compared to the "ideal" output (usually: do they match?). This is fine for testing the reasoning and retrieval capabilities of new LLMs. However, when creating a conversational LLM _systems_, we will not have a specific ideal string in mind for every conversational turn.

There are two basic paradigms for use.

Completion:

- _matching_: an LLM is treated as a function. It is given an input prompt or past conversation and produce output text. The output is compared to an "ideal" string. This is useful in contexts where the LLM output has a "right answer", such as with information retrieval or math. The output here is usually pass/match or fail/no-match per example.
- _machine graded_: an LLM output is graded by another LLM according to a rubric. This is useful when the LLM is expected to adhere to (or avoid) general behaviors, such as being polite or avoiding the `yeasayer effect'. The output is a score

"Matching" is probably not as useful for LEVI applications as it is for evaluation of generic LLMs, since we want LLM agents to be conversational, and since most tutors should not immediately give a student the correct answer. However, machine-graded rubrics may well be very useful. This package makes it easy (editing one file) to add your own rubric and evaluate LLM responses against that rubric.

This package also extends the OpenAI Evals library to add generic function-evaluated metrics. Anything you can write as a Python function (calculating string length, Flesch reading ease, or anything you can think of) can be added as an evaluation metric.

## Running

Prior to running, the tool needs to be configured to meet your needs. This includes telling it how to connect to the LLM you want to test, and telling it which tests you want to run.

### Configuration

Step 0: Installation
* Make sure you have Docker Desktop installed and running.

Step 1: Environment file
* Copy `.env-example` to make a new file called `.env`.

Step 2: Data
* Write your data to the `data/test-cases` directory as a file in `jsonl` format. Each exchange between assistant and user should be one line of the file. The format of each line is JSON, with an `input` key, and a corresponding value that consists of a list of turns like the following:

    `{"input": [{"role": "user", "content": "Hi, Nice to meet you!"}, {"role": "assistant", "content": "Nice to meet you, too! How can I help you today?"}]}`


Step 3a (optional):
* Edit `configuration/function_metrics.py` to include any additional metrics you want to evaluate. These functions should accept a string as input, and produce a numeric value as output.

Step 3b (optional):
* Edit `configuration/rubric_metrics.yaml` as desired. Rubrics in this file will be used to evaluate conversations and completions using COT prompting and will output a numeric score.

Step 3c (optional):
* Edit `configuration/completion_functions.py` as desired. These functions accept a `conversation_history` and `model_name` (at minimum) and return a `completion`, that is, the next turn in the conversation.

Step 4:
* Define a test suite in `evals.yaml`. A test suite includes:
    * an input dataset in `data/test-cases`
    * a list of function metrics to use for scoring (can be blank). These functions must all be defined in `configuration/function_metrics.py`. These have an additional key called `score`, which can have values `completion` or `all_by_role`. The value `completion` will elicit a completion from the LLM specified in the `completions` section of the suite and calculate a metric for that only. The `all_by_role` will calculate a metric value for every existing turn in the conversation, and then the aggregation will be done by role.
    * a list of rubric metrics to use for scoring (can be blank). These must all be defined in `configuration/rubric_metrics.yaml`.
    * an LLM to use for rubric-based grading. Currently only OpenAI models are supported.
    * an LLM to use for `completions`, and associated required parameters. This is the connetion with the LLM system you would like to test. The configuration options specified here will be passed as arguments to the associated function in `configuration/completion_functions.py`.

### Running tests

The scoring service is defined in the `docker-compose.yml` file by `llm-evals`. This runs once per invocation. Build the service by calling:
    `docker-compose build llm-evals`

Then run by calling:
    `docker-compose run llm-evals python main.py YOUR_TEST_SUITE_NAME`
where `YOUR_TEST_SUITE_NAME` is the name of a test suite configuration in

This will run the set of evaluations against the dataset you provided. Results will be stored in two places. First, raw OpenAI Evals outputs will be sent to `data/results/evals-outputs`. Second, data will be saved in table form in the `data/results/results.db` sqlite file.  Optionally, results can also be saved to an Elasticsearch database. See below for more information about this option.

You can re-run evaluations as needed.

### Interpreting results

A "run" consists of a single metric calculated on a single dataset. Metrics are calculated for each conversation in that dataset. Individual metrics are saved alongside an aggregate score for the dataset.

Each file in `data/results/evals-outputs` corresponds to a single run. The first line describes metadata for the overall run - which dataset was used, which completion function was used, which metric was calculated, and more. The second line contains the aggregate metrics. All lines below capture individual calculations, called `events`, for the evaluation. These include (where applicable) the text completions (called `samples`) collected from the completion LLM, the text output of the rubric grader, and the score provided by the rubric or metric functions.

### Pre-installed functionality

This tool is intended to be somewhat "batteries included". It supports the following out-of-the-box:

* scoring historical conversations - useful for monitoring live systems.
* scoring LLMs:
    * locally hosted and served via the `local-llm-api` service, included in the `docker-compose.yml` file
    * locally hosted and served via an endpoint using something like [LM Studio](https://lmstudio.ai)
    * LLMs accessible by a REST endpoint and accessible via a network call
    * any OpenAI LLM
* a set of included rubrics
* a set of included metrics calculated as Python files
* Kibana for visualizing test outputs (described below)

This list will grow as we add functionality to meet LEVI team needs.

### Running an example

To run the included example evaluation suite, run the following from the terminal:

    docker-compose run llm-evals python main.py example

Raw results will be saved in `data/results/evals-outputs/`, and tabular results will be saved in `data/results/results.db` for querying. 

### Plotting results

TODO

### Structure

TODO
