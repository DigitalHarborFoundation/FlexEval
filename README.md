# FlexEval LLM Evals

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.12729993.svg)](https://doi.org/10.5281/zenodo.12729993)
[![License](https://img.shields.io/github/license/DigitalHarborFoundation/FlexEval)](https://github.com/DigitalHarborFoundation/FlexEval/blob/main/LICENSE)

![FlexEval banner](/docs/_static/flexeval_banner.svg)

FlexEval is a tool for designing custom metrics, completion functions, and LLM-graded rubrics for evaluating the behavior of LLM-powered systems.

Additional details about FlexEval can be found [in our paper](/EDM_2024_FlexEval.pdf) at the _Educational Data Mining_ 2024 conference.

Documentation: <https://digitalharborfoundation.github.io/FlexEval>

## Usage

Basic usage: 

```python
import flexeval
from flexeval.schema import Eval, EvalRun, FileDataSource, Metrics, FunctionItem, Config

data_sources = [FileDataSource(path="vignettes/conversations.jsonl")]
eval = Eval(metrics=Metrics(function=[FunctionItem(name="flesch_reading_ease")]))
config = Config(clear_tables=True)
eval_run = EvalRun(
    data_sources=data_sources,
    database_path="eval_results.db",
    eval=eval,
    config=config,
)
flexeval.run(eval_run)
```

This example computes [Flesch reading ease](https://en.wikipedia.org/wiki/Flesch%E2%80%93Kincaid_readability_tests#Flesch_reading_ease) for every turn in a list of conversations provided in JSONL format. The metric values are stored in an SQLite database called `eval_results.db`.

See additional usage examples in the [vignettes](/vignettes).

## Installation

You can install FlexEval from the GitHub repository. FlexEval is not yet available on PyPI.

Using `pip`:

```bash
pip install python-flexeval
```

Using `uv`:

```bash
uv add python-flexeval
```

Using `poetry`:

```bash
poetry add python-flexeval
```

## Why create FlexEval?

_To make evaluations easier for LLM-powered systems._

Thoroughly evaluating LLMs is difficult and best-practices are rapidly developing. While it is not yet clear how to _guarantee_ the behavior of LLM-powered systems, we can absolutely increase visibility into their behavior. Which features are important depends on the application, but might include:

- safety
- verbosity
- use of emojis
- text complexity and reading ease
- appropriateness of function calling
- other things we haven't thought of

The most common method of evaluating LLMs is to prompt them and compare their responses to "ideal" responses. This is necessary for many applications, but is not sufficient to cover the cases above. Moreover, we're confident that as users continue to develop LLM-powered applications, they will want to compute metrics of their own devising to quantify and track the behavior of these applications during development and in production.

With this in mind, we've created a tool that makes it easier to write and apply custom metrics to conversations.

## What is FlexEval?

_FlexEval is a tool for applying functions that produce quantitative metrics to conversational data._

Inputs:

- historical conversations
- Python functions that convert conversations and conversational turns into numbers
- rubrics that an LLM can use to convert conversations and conversational turns into numbers
- configurations for LLMs you would like to test

Process:

- (optional) generate conversational completions using an LLM or LLM-powered system
- apply each Python function to each conversation/turn/completion

Outputs:

- metric values in an SQLite database

## How does FlexEval work?

_FlexEval evaluates Python functions and machine-graded rubrics for each provided conversation._

FlexEval began as an extension to [OpenAI Evals](https://github.com/openai/evals), making it easier to use. It is now independent of OpenAI Evals and offers several usability improvements:

1. Whereas OpenAI Evals requires users to write a new class with inheritance to define new completion functions (a generic term to a function that accepts a conversation or prompt and produces a response), FlexEval allows users to define this using a function in `configuration/completion_functions.py`.
2. Whereas OpenAI Evals requires users to create a new class with inheritance to define a new metric type, FlexEval allows users to do this by writing a function in `configuration/function_metrics.py`.
3. FlexEval makes it easy to use any LLM as a rubric-based grader.
4. FlexEval makes it easy to write eval suites, that is, sets of multiple metrics to be evaluated against the same dataset of conversations.
5. FlexEval allows metrics to be computed over entire conversations (i.e. how many turns are in this conversation), conversations faceted by role (how many turns per role are in this conversation), or individual turns faceted by role (what is the length of each string), and then aggregated (what is the average length of text output produced by the user vs the assistant).

## Running

Prior to running an evaluation, you'll need to tell FlexEval which metrics you want to compute and what conversations you want to use.

- Write your data as a file in `jsonl` format. 
(In the future, we will support other formats and streaming inputs.) 
Each separate _thread_ – one conversation between a user and an assistant – should be one line of the file. 
The format of each line is JSON, with an `input` key, and a corresponding value that consists of a list of turns like the following:

  `{"input": [{"role": "user", "content": "Hi, Nice to meet you!"}, {"role": "assistant", "content": "Nice to meet you, too! How can I help you today?"}]}`

- Add any Python modules containing function metrics to your configuration. Existing function metrics can be viewed in [`flexeval.configuration.function_metrics`](/src/flexeval/configuration/function_metrics.py).

- If desired, create any rubric metrics in a `rubric_metrics.yaml` file. Rubrics in this file will be used to evaluate conversations and completions using "chain-of-thoughts then classify" (COT classify) and will report a numeric score (e.g., 0 or 1) mapped to a choice string (e.g.,"Yes", "No") from the classification results. For more information on how to write and use rubrics in FlexEval, see the [Custom Rubric](/vignettes/custom_rubric.md) vignette.

- Run the evaluation in Python code or via the CLI.

### Running an evaluation within Python

See the vignettes.

### Running an evaluation via CLI

See the [command-line interface](/vignettes/basic_cli.md) vignette.

Or, access the CLI documentation by invoking the module:

```bash
python -m flexeval --help
```

### Interpreting results

Results are saved in an SQLite database. See the [Metric Analysis](/vignettes/metric_analysis.ipynb) vignette for a sample analysis demonstrating the structure and utility of the data saved by FlexEval.

### Pre-installed functionality

This tool is intended to be "batteries included" for many basic use cases. It supports the following out-of-the-box:

- scoring historical conversations - useful for monitoring live systems.
- scoring LLMs:
  - locally hosted and served via an endpoint using something like [LM Studio](https://lmstudio.ai)
  - LLMs accessible by a REST endpoint and accessible via a network call
  - any OpenAI LLM
- a set of useful rubrics
- a set of useful Python functions

## Cite this work

If this work is useful to you, please cite [our EDM 2024 paper](https://educationaldatamining.org/edm2024/proceedings/2024.EDM-posters.107/2024.EDM-posters.107.pdf):

>S. Thomas Christie, Baptiste Moreau-Pernet, Yu Tian, & John Whitmer. (2024). FlexEval: a customizable tool for chatbot performance evaluation and dialogue analysis. _Proceedings of the 17th International Conference on Educational Data Mining_, 903-908. Atlanta, Georgia, USA, July 2024. <https://doi.org/10.5281/zenodo.12729993>

## Code abstractions

FlexEval is a tool for executing _evaluations_.

An evaluation is represented by `flexeval.schema.eval_schema.Eval`, and contains a set of `flexeval.schema.eval_schema.MetricItem`s to apply to the test data.

 - Functions: `flexeval.schema.eval_schema.FunctionItem`s apply a Python function to the test data, returning a numeric value.
 - Rubrics: `flexeval.schema.eval_schema.RubricItem`s use a configured `GraderLlm` function and the provided rubric template to generate a numeric score from an LLM's output.

You execute an `Eval` by creating an `EvalRun`. `flexeval.schema.evalrun_schema.EvalRun` contains:
- Data sources (conversations as inputs, an SQLite filepath as output)
- An `Eval` specification, containing the metrics to compute
- Sources for the metrics defined in the `Eval` e.g. Python modules containing the functions referenced in `FunctionItem`s or YAML files containing the rubric templates.
- A `Config` specification, describing how evaluation should be executed.

The `Config` includes details about multi-threaded metric computation, about logging, etc.

### Data Hierarchy
Metrics can operates at any of four levels of granularity:
- **Thread**: Full conversation
- **Turn**: Adjacent set of messages from the same user or assistant
- **Message**: Individual message from user or assistant
- **ToolCall**: Function/tool invocation within a message

### Logging

FlexEval uses Python's [`logging`](https://docs.python.org/3/library/logging.html).

If you don't want to see FlexEval's logs:

```python
# turn of all INFO and DEBUG log messages, but leave WARNING and ERROR messages
logging.getLogger('flexeval').setLevel(logging.WARNING)
# turn off all logging, including warnings and errors
logging.getLogger('flexeval').setLevel(logging.CRITICAL + 1)
```

## Development

Pull requests to expand the set of provided rubrics or functions are welcome.

To develop FlexEval, you should [install `uv`](https://docs.astral.sh/uv/getting-started/installation/):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Making a build

```bash
uv build
```

### Running tests

Run the unit tests:

```bash
uv run python -m unittest discover -s tests.unit
```

To run a specific file's tests:

```bash
uv run python -m unittest tests.unit.{module_name}
```

There are integration tests in tests/integration that can be executed.

### Adding or updating dependencies

To add a dependency:

```bash
uv add {package_name}
```

To update dependencies:

```bash
uv lock --upgrade
```

Verify CLI:

```bash
uv run python -m flexeval --help
```

### Formatting code files

We format code files using [`ruff`](https://github.com/astral-sh/ruff).

```bash
uvx ruff check --fix
uvx ruff format
```

## Command-line Interface (CLI)

FlexEval exposes a CLI.

### Running an eval set with env variables

Run an eval set by specifying the .env file:

```bash
uv run --env-file=.env python -m flexeval --eval_name {eval_suite_name}
```

Or set the UV_ENV_FILE variable first:

```bash
export UV_ENV_FILE=.env
uv run python -m flexeval --eval_name {eval_suite_name}
```


## Documentation

We use Sphinx to generate docs.

Developing the docs website:

```bash
uv run sphinx-autobuild docs build
```
