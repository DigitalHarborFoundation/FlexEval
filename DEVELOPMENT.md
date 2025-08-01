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

Are you using the pre-commits and want to push a commit that doesn't pass the pre-commit checks?
No problem, happens to the best of us:

```bash
git commit --no-verify
```

Update the pre-commit versions used occasionally:

```bash
uv run pre-commit autoupdate
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

You can also just build the site directly:
```bash
make html
```

## Releasing a new version

 1. Create and merge a PR from `dev` to `main`.
 2. Check that the GitHub Actions jobs complete successfully (particularly the push to TestPyPI).
 3. Create a new release: <https://github.com/DigitalHarborFoundation/FlexEval/releases/new>
     1. Set release title to "vX.X.X", with the appropriate version from the `pyproject.toml` file.
     2. Create a new tag "vX.X.X", with the appropriate version from the `pyproject.toml` file.
     3. Click "Generate release notes" (and make any additional edits if necessary).
     4. Click "Publish release".
 4. Verify that the GitHub Actions completes successfully and that the new release is available on PyPI.

A few notes:
 - This process is overly manual at the moment. Plausibly, we should update the GitHub Action to push to TestPyPI for every commit on any PR that targets `main` (but not any tags). Then, only push to PyPI on tags.
 - We could in the future automatically make a release using the GitHub API when a PR is merged to `main`. For now, this manual process requires us to validate before each release.
 - We should potentially add a new step to the PyPI release that installs `python-flexeval` from PyPI and runs the *.py vignettes, to ensure the new release is actually installable via `pip`.
