# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Environment Setup
```bash
# Install uv package manager first: https://docs.astral.sh/uv/getting-started/installation/
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync
```

### Running FlexEval

Not quite ready; our refactor is close to being done.

```bash
# CLI help
uv run python -m flexeval --help
```

### Testing
```bash
# Run unit tests
uv run python -m unittest discover -s tests.unit

# Run specific test file
uv run python -m unittest tests.unit.{module_name}

# Integration tests are in tests/integration/, but aren't ready yet
```

### Build and Dependencies
```bash
# Build the package
uv build

# Add dependency
uv add {package_name}

# Update dependencies
uv lock --upgrade
```

### Linting
```bash
# Run ruff linter (configured in ruff.toml)
ruff check src/
ruff format src/
```

## Architecture Overview

FlexEval is a tool for evaluating LLM-powered systems using custom metrics, completion functions, and LLM-graded rubrics. The system operates on conversational data at multiple granularities.

### Core Abstractions

**EvalRun** (`src/flexeval/schema/evalrun_schema.py`): The top-level execution unit that combines:
- Data sources (conversations in JSONL format as inputs, an SQLite filepath as output)
- An Eval specification (metrics to compute)
- Configuration (workers, database path, etc.)
- Rubric and function sources

**Eval** (`src/flexeval/schema/eval_schema.py`): Defines what to evaluate:
- Function metrics (Python functions that compute numeric values)
- Rubric metrics (LLM-graded evaluations using chain-of-thought)
- Completion LLM (for generating new responses)
- Grader LLM (for rubric evaluation)
- Dependencies between metrics

**Config** (`src/flexeval/schema/config_schema.py`): Defines how to evaluate (e.g. single- vs multi-process, etc.)

### Data Hierarchy
The evaluation operates at multiple levels of granularity:
- **Thread**: Full conversation
- **Turn**: User-assistant exchange pair  
- **Message**: Individual message from user or assistant
- **ToolCall**: Function/tool invocation within a message

### Key Components

**Configuration System**:
- `src/flexeval/configuration/rubric_metrics.yaml`: Default set of rubrics
- `src/flexeval/configuration/function_metrics.py`: Default set of Python metric functions
- `src/flexeval/configuration/completion_functions.py`: Set of functions for producing LLM completions (usually via API call)

**Execution Pipeline** (`src/flexeval/runner.py`):
1. Load configuration and eval specification
2. Create Dataset from data sources
3. Run EvalRunner to compute metrics
4. Store results in SQLite database

**Metric System**:
- Function metrics: Python functions that analyze conversations/turns/messages
- Rubric metrics: LLM-based evaluations using structured prompts
- Dependencies: Metrics can depend on other metrics meeting certain criteria
- Aggregation: Results aggregated by role, turn, etc.

### Data Format

Input data is in JSONL format with conversations as:
```json
{"input": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}
```

Results are stored in an SQLite database (defaulting to `data/results/results.db`) for querying and analysis.

### Schema System

The project uses Pydantic models for validation:
- `src/flexeval/schema/`: Contains all schema definitions
