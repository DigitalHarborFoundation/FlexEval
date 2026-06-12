#!/usr/bin/env python
"""Post-publish smoke test for the installed ``python-flexeval`` package.

This is intentionally a standalone script with no dependencies beyond the
standard library and an *installed* ``flexeval``. It is meant to be run inside a
clean environment (a fresh venv, ``uvx``, or CI) against the published wheel to
verify that the artifact actually installs and runs -- catching problems that
local, source-tree testing cannot, e.g.:

  - data files (``rubric_metrics.yaml``, ``evals.yaml``) missing from the wheel
  - missing/incorrect runtime dependencies
  - a broken ``flexeval`` console-script entry point

It deliberately does NOT hit any network or LLM API, so it is safe to run in CI
without credentials.

Usage::

    python scripts/smoke_test.py                 # just run the checks
    python scripts/smoke_test.py --expect-version 0.5.0   # also assert version
    python scripts/smoke_test.py --run-vignettes          # also run vignettes/*.py

The script exits non-zero on the first failed check.

``--run-vignettes`` executes the documented usage examples in ``vignettes/*.py``
end-to-end against the *installed* package, verifying that the primary examples
shown in the docs actually work. This check requires the repository to
be checked out (the vignettes read/write files relative to the repo root), so it
must be run with the repo root as the working directory and is kept opt-in.
"""

import argparse
import importlib.resources
import subprocess
import sys
from pathlib import Path


def fail(message: str) -> "NoReturn":  # type: ignore[name-defined]
    print(f"FAIL: {message}")
    sys.exit(1)


def check(description: str, ok: bool, detail: str = "") -> None:
    status = "ok  " if ok else "FAIL"
    suffix = f" ({detail})" if detail else ""
    print(f"  [{status}] {description}{suffix}")
    if not ok:
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--expect-version",
        default=None,
        help="If set, assert the installed flexeval version matches exactly. "
        "Use this in CI to confirm you are testing the just-published build.",
    )
    parser.add_argument(
        "--run-vignettes",
        action="store_true",
        help="Also run the documented usage examples in vignettes/*.py end-to-end. "
        "Requires the repo to be checked out and the repo root as the working dir.",
    )
    parser.add_argument(
        "--vignettes-dir",
        default="vignettes",
        help="Directory containing the vignette scripts (default: vignettes).",
    )
    args = parser.parse_args()

    print("Running flexeval post-publish smoke test...")

    # 1. The package imports, and we can read its version.
    try:
        import flexeval
    except Exception as e:  # noqa: BLE001 - we want to surface any import error
        fail(f"could not import flexeval: {e!r}")

    version = getattr(flexeval, "__version__", None)
    check("import flexeval", True, f"version={version}")

    if args.expect_version is not None:
        check(
            f"installed version == {args.expect_version}",
            version == args.expect_version,
            f"got {version}",
        )

    # 2. Core runtime deps ship and the metric/class tree imports.
    #    function_metrics pulls in openai, textstat, and flexeval.classes.*,
    #    so a clean import here exercises the core dependency set.
    try:
        from flexeval.configuration import (  # noqa: F401
            completion_functions,
            function_metrics,
        )
    except Exception as e:  # noqa: BLE001
        fail(f"could not import flexeval.configuration submodules: {e!r}")
    check("import flexeval.configuration.{function_metrics,completion_functions}", True)

    # 3. Packaged data files are present in the installed wheel.
    config_files = importlib.resources.files("flexeval.configuration")
    for data_file in ("rubric_metrics.yaml", "evals.yaml"):
        check(
            f"packaged data file present: {data_file}",
            (config_files / data_file).is_file(),
        )

    # 4. The default rubric collection loads and parses (exercises both the
    #    packaged YAML and the pydantic schema).
    try:
        from flexeval import rubric

        collection = rubric.get_default_rubric_collection()
        n_rubrics = len(collection.rubrics)
    except Exception as e:  # noqa: BLE001
        fail(f"could not load default rubric collection: {e!r}")
    check(
        "load default rubric collection",
        n_rubrics > 0,
        f"{n_rubrics} rubrics",
    )

    # 5. The console-script entry point is installed and runnable.
    #    Run as `python -m flexeval` so the check works even if the scripts
    #    dir is not on PATH; this still exercises the same entry point target.
    try:
        result = subprocess.run(
            [sys.executable, "-m", "flexeval", "--help"],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except Exception as e:  # noqa: BLE001
        fail(f"could not invoke `python -m flexeval --help`: {e!r}")
    check(
        "`python -m flexeval --help` exits 0",
        result.returncode == 0,
        f"returncode={result.returncode}",
    )

    # 6. (Optional) Run the documented usage examples end-to-end.
    if args.run_vignettes:
        run_vignettes(Path(args.vignettes_dir))

    print("\nAll smoke-test checks passed.")


def run_vignettes(vignettes_dir: Path) -> None:
    print(f"\nRunning vignettes in {vignettes_dir}/ ...")
    if not vignettes_dir.is_dir():
        fail(
            f"vignettes dir {vignettes_dir} not found "
            "(run from the repo root, or pass --vignettes-dir)"
        )

    scripts = sorted(vignettes_dir.glob("*.py"))
    if not scripts:
        fail(f"no vignette scripts found in {vignettes_dir}")

    for script in scripts:
        # Run from the current working directory (the repo root): the vignettes
        # reference data files via repo-relative paths like
        # "vignettes/conversations.jsonl".
        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            timeout=300,
        )
        ok = result.returncode == 0
        if not ok:
            # Surface the failure output before check() exits the process.
            print(f"--- {script.name} stdout ---\n{result.stdout}")
            print(f"--- {script.name} stderr ---\n{result.stderr}", file=sys.stderr)
        check(f"vignette runs: {script.name}", ok, f"returncode={result.returncode}")


if __name__ == "__main__":
    main()
