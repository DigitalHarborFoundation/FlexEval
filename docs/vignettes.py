from pathlib import Path
import ast
import re

import tokenize
from io import StringIO
import logging

logger = logging.getLogger(__name__)


def extract_top_comments(file_contents: str) -> list[str]:
    comments = []
    tokens = tokenize.generate_tokens(StringIO(file_contents).readline)

    for tok_type, tok_str, start, end, line in tokens:
        if tok_type == tokenize.COMMENT:
            comments.append(tok_str.lstrip("# ").rstrip())
        elif tok_type in {tokenize.NL, tokenize.NEWLINE}:
            continue
        elif tok_type == tokenize.ENCODING:
            continue
        else:
            # First non-comment, non-blank, non-encoding token
            break

    return comments


def extract_vignette_path_strings(file_contents: str) -> list[str]:
    tree = ast.parse(file_contents, filename="vignette.py")
    strings = []

    class StringVisitor(ast.NodeVisitor):
        def visit_Constant(self, node):
            if isinstance(node.value, str) and re.match(
                r'^vignettes/[^"\']+$', node.value
            ):
                strings.append(node.value)

    StringVisitor().visit(tree)
    return strings


def write_if_changed(path: Path, old_content: str, new_content: str):
    if path.exists():
        # check if the file contents are different
        if old_content == new_content:
            return  # No change — don't touch file
    path.write_text(new_content)


def generate_custom_stubs(app):
    """
    builder-inited callback.
    see: https://www.sphinx-doc.org/en/master/extdev/event_callbacks.html
    """
    src_dir = Path(app.srcdir)
    output_dir = src_dir / "generated" / "vignettes"
    vignettes_dir = src_dir.parent / "vignettes"
    if not vignettes_dir.exists():
        raise ValueError(
            f"Expected vignettes directory {vignettes_dir} does not exist."
        )

    output_dir.mkdir(exist_ok=True, parents=True)

    for vignette_file in vignettes_dir.glob("*"):
        stem = vignette_file.stem
        target_file = output_dir / f"{stem}.rst"
        if vignette_file.suffix == ".ipynb":
            target_file = output_dir / f"{stem}.ipynb"

        current_contents = ""
        if target_file.exists():
            current_contents = target_file.read_text()

        if vignette_file.suffix == ".py":
            generate_python_stub(src_dir, vignette_file, target_file, current_contents)
        elif vignette_file.suffix == ".ipynb":
            generate_ipynb_stub(vignette_file, target_file, current_contents)
        elif vignette_file.suffix == ".md":
            generate_md_stub(src_dir, vignette_file, target_file, current_contents)
        else:
            logger.info(
                f"Unsupported file type {vignette_file.suffix}; skipping while creating vignette stubs."
            )


def generate_ipynb_stub(ipynb_file: Path, target_file: Path, current_contents: str):
    # unlike the other file types, we just copy ipynb files
    new_contents = ipynb_file.read_text()
    write_if_changed(target_file, current_contents, new_contents)


def generate_md_stub(
    src_dir: Path, md_file: Path, rst_file: Path, current_contents: str
):
    new_contents = f""".. _{md_file.stem}:
    
.. include:: ../../../{md_file.relative_to(src_dir.parent)}
   :parser: myst_parser.docutils_
"""
    write_if_changed(rst_file, current_contents, new_contents)


def generate_python_stub(
    src_dir: Path, py_file: Path, rst_file: Path, current_contents: str
):
    stem = py_file.stem
    py_file_contents = py_file.read_text()
    other_source_paths = extract_vignette_path_strings(py_file_contents)
    comments = extract_top_comments(py_file_contents)
    title = stem.capitalize().replace("_", " ")
    for i, comment in enumerate(comments):
        if comment.strip().startswith(".. title::"):
            title = comment.split("::")[1].strip()
            comments[i] = ""
            break
    else:
        # skip .py files without titles
        return

    top_comment = " ".join(comments).strip()
    new_contents = f""".. _{py_file.stem}:

{title}
{"=" * len(title)}

{top_comment}

Python source: ``{py_file.name}``

.. literalinclude:: ../../../{py_file.relative_to(src_dir.parent)}
   :language: python
   :linenos:
   :lines: {len(comments) + 1}-
   :lineno-start: 1
"""
    for other_source_path in other_source_paths:
        other_source_path = Path(other_source_path)
        # other_source_contents = other_source_path.read_text()
        new_contents += f"""
``{other_source_path.name}`` contents:

.. literalinclude:: ../../../{other_source_path}
   :language: python
   :linenos:
"""
    write_if_changed(rst_file, current_contents, new_contents)


if __name__ == "__main__":

    class MockApp:
        srcdir = "./docs"

    generate_custom_stubs(MockApp(), None)
