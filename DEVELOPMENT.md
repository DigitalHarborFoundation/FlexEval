# Development

See the README and the [documentation website](https://digitalharborfoundation.github.io/FlexEval) for information about FlexEval.

## Development basics

To develop FlexEval, you should [install `uv`](https://docs.astral.sh/uv/getting-started/installation/):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Installing dependencies

This installs all optional dependencies as well.

```bash
uv sync --all-groups
```

You can force an upgrade for all dependencies:

```bash
uv sync --upgrade --all-groups
```

### Making a build

```bash
uv build
```

### Running tests

Run the unit tests:

```bash
make unittest
# OR
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

You can avoid having to remember this by setting up the pre-commits:

```bash
uv run pre-commit install
# run on any initial files
uv run pre-commit run --all-files
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

We use Sphinx to generate the documentation website.

All of the relevant directives are in the `Makefile`.

Develop the documentation website locally:

```bash
make docclean docautobuild
```
