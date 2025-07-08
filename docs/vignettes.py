import os
from pathlib import Path
import ast
import re


def extract_vignette_path_strings(file_contents: str):
    tree = ast.parse(file_contents, filename="vignette.py")
    strings = []

    class StringVisitor(ast.NodeVisitor):
        def visit_Str(self, node):  # For Python <3.8
            if re.match(r'^vignettes/[^"\']+$', node.s):
                strings.append(node.s)

        def visit_Constant(self, node):  # For Python 3.8+
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


def generate_custom_stubs(app, config):
    """
    config-inited
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
        # TODO designate some kind of comment indicator that shows a thing should be skipped
        other_source_paths = extract_vignette_path_strings(py_file_contents)
        new_contents = f"""
{stem}
{'=' * len(stem)}

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
