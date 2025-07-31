# Motivation

Here, we describe FlexEval at a high level.
Additional details about the motivation and design of FlexEval can be found in our [paper](https://doi.org/10.5281/zenodo.12729993) at the *Educational Data Mining* 2024 conference.


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

## Running an evaluation with FlexEval

Here are the basic steps.

- Prior to running an evaluation, you'll need to tell FlexEval which metrics you want to compute and what conversations you want to use.

- Write your data as a file in `jsonl` format. 
(In the future, we will support other formats and streaming inputs.) 
Each separate _thread_ – one conversation between a user and an assistant – should be one line of the file. 
The format of each line is JSON, with an `input` key, and a corresponding value that consists of a list of turns like the following:

  `{"input": [{"role": "user", "content": "Hi, Nice to meet you!"}, {"role": "assistant", "content": "Nice to meet you, too! How can I help you today?"}]}`

- Add any Python modules containing function metrics to your configuration. Existing function metrics can be viewed in {mod}`flexeval.configuration.function_metrics`.

- If desired, create any rubric metrics in a `rubric_metrics.yaml` file. Rubrics in this file will be used to evaluate conversations and completions using "chain-of-thoughts then classify" (COT classify) and will report a numeric score (e.g., 0 or 1) mapped to a choice string (e.g.,"Yes", "No") from the classification results. For more information on how to write and use rubrics in FlexEval, see the {ref}`Custom Rubric <custom_rubric>` vignette.

- Run the evaluation in Python code or via the CLI.