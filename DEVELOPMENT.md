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

### Unit tests

Unit tests live in `tests/unit/` and are run in CI.

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

### Integration tests

Integration tests live in `tests/integration/` and are **not** run in CI.

Run the integration tests:

```bash
uv run python -m unittest tests.integration.functional_tests
```

**Prerequisites:**
- An `.env` file at the repo root with `OPENAI_API_KEY` set
- Suites with rubric metrics (`TestSuite04`) make **real API calls** to OpenAI (gpt-5.4-nano)
- Function-only suites (`TestSuite01`, `TestSuite02`, `TestSuite03`) do not require API keys
- LangGraph-based test suites use pre-generated test data from `tests/resources/langgraph-test-data.db`

To run only the function-metric suites (no API key required):

```bash
uv run python -m unittest tests.integration.functional_tests.TestSuite01 tests.integration.functional_tests.TestSuite02 tests.integration.functional_tests.TestSuite03
```

**Regenerating LangGraph test data:**

The file `tests/resources/langgraph-test-data.db` is pre-generated. To regenerate it (requires `OPENAI_API_KEY`):

```bash
uv run python tests/integration/langgraph_data.py
```

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

The package version lives in `src/flexeval/__about__.py` (`pyproject.toml` reads it
dynamically). The [`deploy-to-pypi`](.github/workflows/deploy-to-pypi.yml) workflow
behaves differently depending on what triggered it:

 - **Every push to `main`** builds the distribution (so build breakage is caught early).
 - **A push to `main` that bumps the version** additionally publishes to TestPyPI and
   runs the smoke test against it (see [Post-publish smoke test](#post-publish-smoke-test)).
   TestPyPI rejects re-uploading an existing version, so the publish/smoke-test steps are
   gated on the version actually changing — non-bump commits (e.g. dependabot merges) only build.
 - **A tag push (`v*`)** publishes to the real PyPI and runs the smoke test against that release.

To cut a release:

 1. Bump the version in `src/flexeval/__about__.py` and merge a PR to `main`.
 2. Check that the GitHub Actions jobs complete successfully — in particular that the
    `publish-to-testpypi` and `smoke-test-testpypi` jobs ran and passed (they only run
    when the version changed).
 3. Create a new release: <https://github.com/DigitalHarborFoundation/FlexEval/releases/new>
     1. Set release title to "vX.X.X", with the version from `src/flexeval/__about__.py`.
     2. Create a new tag "vX.X.X", with the version from `src/flexeval/__about__.py`.
     3. Click "Generate release notes" (and make any additional edits if necessary).
     4. Click "Publish release".
 4. Verify that the GitHub Actions complete successfully — including `smoke-test-pypi` —
    and that the new release is available on PyPI.

A few notes:
 - This process is more manual than it could be. We could in the future automatically make
   a release using the GitHub API when a version bump is merged to `main`. For now, this
   manual process requires us to validate before each release.

### Post-publish smoke test

`scripts/smoke_test.py` verifies that a *published* build actually installs and runs in a
clean environment — catching problems that local, source-tree testing misses (data files
dropped from the wheel, missing runtime deps, a broken `flexeval` entry point). It runs
automatically after both the TestPyPI and PyPI publishes, but you can also run it manually
against any published build, e.g. to sanity-check a release:

```bash
# Against the latest release on PyPI, in a throwaway environment:
uvx --from python-flexeval python scripts/smoke_test.py --run-vignettes

# Or explicitly, into a fresh venv (pin the version to be sure which build you test):
uv venv /tmp/smoke-env
uv pip install --python /tmp/smoke-env python-flexeval==X.Y.Z
/tmp/smoke-env/bin/python scripts/smoke_test.py --expect-version X.Y.Z --run-vignettes
```

`--run-vignettes` runs every `vignettes/*.py` end-to-end against the installed package, so
the docs' primary usage examples are exercised against the real build. It must be run from
the repo root (the vignettes reference repo-relative paths).
