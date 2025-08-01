# FlexEval LLM Evals

[![PyPi](https://img.shields.io/pypi/v/python-flexeval)](https://pypi.org/project/python-flexeval/)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.12729993.svg)](https://doi.org/10.5281/zenodo.12729993)
[![License](https://img.shields.io/github/license/DigitalHarborFoundation/FlexEval)](https://github.com/DigitalHarborFoundation/FlexEval/blob/main/LICENSE)
[![GitHub issues](https://img.shields.io/badge/issue_tracking-github-blue.svg)](https://github.com/DigitalHarborFoundation/FlexEval/issues)

![FlexEval banner](https://raw.githubusercontent.com/DigitalHarborFoundation/FlexEval/refs/heads/main/docs/_static/flexeval_banner.svg)

FlexEval is a tool for designing custom metrics, completion functions, and LLM-graded rubrics for evaluating the behavior of LLM-powered systems.

**Documentation:** <https://digitalharborfoundation.github.io/FlexEval>

Additional details about FlexEval can be found [in our paper](https://doi.org/10.5281/zenodo.12729993) at the _Educational Data Mining_ 2024 conference.

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

See additional usage examples in the [vignettes](https://github.com/DigitalHarborFoundation/FlexEval/tree/main/vignettes).

## Installation

FlexEval is on PyPI as [`python-flexeval`](https://pypi.org/p/python-flexeval). See the [Installation](https://digitalharborfoundation.github.io/FlexEval/getting_started.html#Installation) section in the [Getting Started](https://digitalharborfoundation.github.io/FlexEval/getting_started.html) guide.

Using `pip`:

```bash
pip install python-flexeval
```

## Basic functionality

FlexEval is designed to be "batteries included" for many basic use cases. It supports the following out-of-the-box:

- scoring historical conversations - useful for monitoring live systems.
- scoring LLMs:
  - locally hosted and served via an endpoint using something like [LM Studio](https://lmstudio.ai)
  - LLMs accessible by a REST endpoint and accessible via a network call
  - any OpenAI LLM
- a set of useful rubrics
- a set of useful Python functions

Evaluation results are saved in an SQLite database. See the [Metric Analysis](https://digitalharborfoundation.github.io/FlexEval/generated/vignettes/metric_analysis.html) vignette for a sample analysis demonstrating the structure and utility of the data saved by FlexEval.


Read more in the [Getting Started](https://digitalharborfoundation.github.io/FlexEval/getting_started.html) guide.

## Cite this work

If this work is useful to you, please cite [our EDM 2024 paper](https://educationaldatamining.org/edm2024/proceedings/2024.EDM-posters.107/2024.EDM-posters.107.pdf):

>S. Thomas Christie, Baptiste Moreau-Pernet, Yu Tian, & John Whitmer. (2024). FlexEval: a customizable tool for chatbot performance evaluation and dialogue analysis. _Proceedings of the 17th International Conference on Educational Data Mining_, 903-908. Atlanta, Georgia, USA, July 2024. <https://doi.org/10.5281/zenodo.12729993>

## Development

Pull requests are welcome. Feel free to contribute:
- New rubrics or functions
- Bug fixes
- New features

See [DEVELOPMENT.md](https://github.com/DigitalHarborFoundation/FlexEval/tree/main/DEVELOPMENT.md).
