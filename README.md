# FlexEval LLM Evals

Author: Thomas Christie

FlexEval is a wrapper for OpenAI Evals that makes it easier to design custom metrics, completion functions, and LLM-graded rubrics for evaluating the behavior of LLM-powered systems.

## Why?

_To make evaluations easier for LLM-powered systems._

Thoroughly evaluating LLMs is difficult and best-practices are rapidly developing. While it is not yet clear how to _guarantee_ the behavior of LLM-powered systems, we can absolutely increase visibility into their behavior. Which features are important depends on the application, but might include:

- safety
- verbosity
- use of emojis
- text complexity and reading ease
- appropriateness of function calling
- other things we haven't thought of

The most common method of evaluating LLMs is to prompt them and compare their responses to "ideal" responses. This is necessary for many applications, but is not sufficient to cover the cases above. Moreover, we're confident that as users continue to develop LLM-powered applications, they will desire to collect metrics of their own devising to quantify and track the behavior of these applications during development and in production.

With this in mind, we've created a tool that makes it easier to write custom metrics on conversations and completions.

## What?

_FlexEval is a tool for writing metrics that produce quantitative metrics on conversational data._

Inputs:

- historical conversations
- Python functions that convert conversations and conversational turns into numbers
- configurations for LLMs you would like to test

Process:

- (optional) generate conversational completions using an LLM or LLM-powered system
- apply each Python function to each conversation/turn/completion

Outputs:

- json files
- entries in a SQLite database that can be queried

## How

_FlexEval converts settings into OpenAI Evals configurations_

FlexEval is an interface for OpenAI Evals to make it simpler to use. It does this in several ways. The common thread is that users can extend OpenAI Evals to meet their needs without needing to understand the directory structure, class structure, or internal logic of OpenAI Evals.

1. Whereas OpenAI Evals requires users to write a new class with inheritance to define new completion functions (a generic term to a function that accepts a conversation or prompt and produces a response), FlexEval allows users to define this using a function in `configuration/completion_functions.py`.
2. Whereas OpenAI Evals requires users to create a new class with inheritance to define a new metric type, FlexEval allows users to do this by writing a function in `configuration/function_metrics.py`.
3. FlexEval makes it easy to use any LLM as a rubric-based grader.
4. FlexEval makes it easy to write test suites, that is, sets of multiple metrics to be evaluated against the same dataset of conversations.
5. FlexEval allows metrics to be computed over entire conversations (i.e. how many turns are in this conversation), conversations faceted by role (how many turns per role are in this conversation), or individual turns faceted by role (what is the length of each string), and then aggregated (what is the average length of text output produced by the user vs the assistant).

$${\color{red}\textsf{WARNING: FlexEval is under early and active development. The following README will change frequently.}}$$

$${\color{red}\textsf{Expect breaking changes. We will establish a versioning system soon.}}$$

## Running

Prior to running, the tool needs to be configured to meet your needs. This includes telling it how to connect to the LLM you want to test, and telling it which tests you want to run.

### Configuration

Step 0: Installation

- Make sure you have Docker Desktop installed and running.

Step 1: Environment file

- Copy `.env-example` to make a new file called `.env`.

Step 2: Data

- Write your data to the `data/test-cases` directory as a file in `jsonl` format. Each exchange between assistant and user should be one line of the file. The format of each line is JSON, with an `input` key, and a corresponding value that consists of a list of turns like the following:

  `{"input": [{"role": "user", "content": "Hi, Nice to meet you!"}, {"role": "assistant", "content": "Nice to meet you, too! How can I help you today?"}]}`

Step 3a (optional):

- Edit `configuration/function_metrics.py` to include any additional function metrics. These functions can process either a single conversational turn or an entire conversation. To better understand the input and output options for these functions, see function templates in `configuration/completion_functions.py`.

Step 3b (optional):

- Edit `configuration/rubric_metrics.yaml` as desired. Rubrics in this file will be used to evaluate conversations and completions using COT prompting. Check [here](https://github.com/openai/evals/blob/d3dc89042ddee879a68a326fdb37716ee518640c/docs/eval-templates.md) for some rubric writing guidelines and templates.

Step 3c (optional):

- Edit `configuration/completion_functions.py` as desired. These functions accept a `conversation_history` and `model_name` (at minimum) and return a `completion`, that is, the next turn in the conversation.

Step 4:

- Define a test suite in `evals.yaml`. A test suite includes:
- an input dataset in `data/test-cases`
- a list of function metrics to use for scoring (can be blank). These functions must all be defined in `configuration/function_metrics.py`. These have an additional key called `score`, which can have values `completion` or `all_by_role`. The value `completion` will elicit a completion from the LLM specified in the `completions` section of the suite and calculate a metric for that only. The `all_by_role` will calculate a metric value for every existing turn in the conversation, and then the aggregation will be done by role.
- a list of rubric metrics to use for scoring (can be blank). These must all be defined in `configuration/rubric_metrics.yaml`.
- an LLM to use for rubric-based grading. Currently only OpenAI models are supported.
- an LLM to use for `completions`, and associated required parameters. This is the connetion with the LLM system you would like to test. The configuration options specified here will be passed as arguments to the associated function in `configuration/completion_functions.py`.

### Running tests

The scoring service is defined in the `docker-compose.yml` file by `llm-evals`. This runs once per invocation. Build the service by calling:
`docker-compose build llm-evals`

Then run by calling:
`docker-compose run llm-evals python main.py YOUR_TEST_SUITE_NAME`
where `YOUR_TEST_SUITE_NAME` is the name of a test suite configuration in

This will run the set of evaluations against the dataset you provided. Results will be stored in two places. First, raw OpenAI Evals outputs will be sent to `data/results/evals-outputs`. Second, data will be saved in table form in the `data/results/results.db` sqlite file. Optionally, results can also be saved to an Elasticsearch database. See below for more information about this option.

You can re-run evaluations as needed.

### Interpreting results

A "run" consists of a single metric calculated on a single dataset. Metrics are calculated for each conversation in that dataset. Individual metrics are saved alongside an aggregate score for the dataset.

Each file in `data/results/evals-outputs` corresponds to a single run. The first line describes metadata for the overall run - which dataset was used, which completion function was used, which metric was calculated, and more. The second line contains the aggregate metrics. All lines below capture individual calculations, called `events`, for the evaluation. These include (where applicable) the text completions (called `samples`) collected from the completion LLM, the text output of the rubric grader, and the score provided by the rubric or metric functions.

### Pre-installed functionality

This tool is intended to be somewhat "batteries included". It supports the following out-of-the-box:

- scoring historical conversations - useful for monitoring live systems.
- scoring LLMs:
- locally hosted and served via the `local-llm-api` service, included in the `docker-compose.yml` file
- locally hosted and served via an endpoint using something like [LM Studio](https://lmstudio.ai)
- LLMs accessible by a REST endpoint and accessible via a network call
- any OpenAI LLM
- a set of included rubrics
- a set of included metrics calculated as Python files
- Metabase for visualizing test outputs (described below)

This list will grow as we add functionality to meet LEVI team needs.

### Running an example

To run the included example evaluation suite, run the following from the terminal:

docker-compose run llm-evals python main.py example

Raw results will be saved in `data/results/evals-outputs/`, and tabular results will be saved in `data/results/results.db` for querying.

```

```
