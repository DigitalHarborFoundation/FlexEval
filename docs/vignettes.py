from pathlib import Path
import ast
import re

import tokenize
from io import StringIO


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
        old_content = path.read_text()
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
    target_dir = src_dir.parent / "vignettes"

    output_dir.mkdir(exist_ok=True, parents=True)

    for py_file in target_dir.glob("*.py"):
        stem = py_file.stem
        rst_file = output_dir / f"{stem}.rst"

        current_contents = ""
        if rst_file.exists():
            current_contents = rst_file.read_text()
        py_file_contents = py_file.read_text()
        other_source_paths = extract_vignette_path_strings(py_file_contents)
        comments = extract_top_comments(py_file_contents)
        if len(comments) > 0:
            top_comment = " ".join(comments)
        else:
            continue

        new_contents = f"""
{stem}
{'=' * len(stem)}

{top_comment}

Python source: ``{py_file.name}``

.. literalinclude:: ../../../{py_file.relative_to(src_dir.parent)}
   :language: python
   :linenos:
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
        # TODO for each other referenced source path, do a literal include
        write_if_changed(rst_file, current_contents, new_contents)


if __name__ == "__main__":

    class MockApp:
        srcdir = "./docs"

    generate_custom_stubs(MockApp(), None)
