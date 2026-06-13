# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html
import sys
import os

import peewee as pw

sys.path.append(os.path.abspath("."))
sys.path.append(".")

import vignettes

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "FlexEval"
copyright = "2025, Digital Harbor Foundation"
author = "S. Thomas Christie, Baptiste Moreau-Pernet, Zachary Levonian, Anna Rafferty, Terry Yu Tian"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.inheritance_diagram",  # class diagrams on the API page (needs Graphviz)
    "sphinx.ext.intersphinx",
    "sphinx.ext.napoleon",  # Google-style docstrings
    "sphinxext.github",
    "sphinx_copybutton",
    # "myst_parser",  # don't use myst_parser with myst_nb; it is automatically loaded by myst_parser
    "myst_nb",
    "sphinxcontrib.autodoc_pydantic",  # because sphinx plays badly with pydantic
    "sphinx.ext.viewcode",  # adds a "[source]" link next to documented objects
    "sphinxcontrib.programoutput",  # for inline bash execution
]
source_suffix = {
    ".rst": "restructuredtext",
    ".ipynb": "myst-nb",
    ".md": "myst-nb",
}

templates_path = ["_templates"]
exclude_patterns = []


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "pydata_sphinx_theme"
html_static_path = ["_static"]
html_logo = "_static/flexeval_logo.png"
html_theme_options = {
    "logo": {
        "text": "FlexEval",
        "image_light": "_static/flexeval_logo.png",
        "image_dark": "_static/flexeval_logo.png",
    },
    "use_edit_page_button": True,
    "primary_sidebar_end": ["indices.html"],
}
html_favicon = "_static/flexeval_favicon.svg"
html_context = {
    "github_user": "DigitalHarborFoundation",
    "github_repo": "FlexEval",
    "github_version": "main",
    "doc_path": "docs",
}
github_project_url = "https://github.com/DigitalHarborFoundation/FlexEval/"

intersphinx_mapping = {
    "pandas": ("https://pandas.pydata.org/pandas-docs/stable/", None),
    "python": ("https://docs.python.org/3/", None),
    "peewee": ("https://docs.peewee-orm.com/en/latest/", None),
    "pydantic": ("https://docs.pydantic.dev/latest", None),
}

# myst-parser
# https://myst-parser.readthedocs.io/en/latest/configuration.html
myst_gfm_only = False
# https://myst-nb.readthedocs.io/en/latest/authoring/jupyter-notebooks.html
myst_enable_extensions = [
    "amsmath",
    "colon_fence",
    "deflist",
    "dollarmath",
    "html_image",
]
myst_url_schemes = ("http", "https", "mailto")

# myst-nb configuration
nb_execution_mode = "off"  # Don't re-execute, use existing outputs
nb_merge_streams = True

autosummary_generate = True
autodoc_typehints = "signature"
# Some models hold fields that have no JSON-schema representation (e.g.
# FunctionsCollection.functions is a list[Callable]). Coerce rather than warn so
# autodoc-pydantic renders a schema for the serializable fields instead of
# emitting a build warning for the model.
autodoc_pydantic_model_show_json_error_strategy = "coerce"
autodoc_default_options = {
    "members": True,
    "undoc-members": True,
    "show-inheritance": True,
    "inherited-members": False,
    "exclude-members": "model_parametrized_name",
}


def skip_peewee_internals(app, what, name, obj, skip, options):
    """Hide peewee-generated noise from the API docs.

    peewee's model metaclass adds several kinds of members to every model class
    that aren't useful in the generated reference:

    - a per-model ``DoesNotExist`` exception (e.g. ``MetricDoesNotExist``),
    - a ``<fk>_id`` alias for every foreign key (e.g. ``dataset_id`` alongside
      ``dataset``). The alias shares the same ``Field`` object as the FK, whose
      ``.name`` is the FK field name, so we can detect it by name mismatch, and
    - a back-reference accessor for every relation pointing at the model (e.g.
      ``Dataset.messages`` from ``Message.dataset``). These render as bare names
      with no docstring or type, and they trip docutils warnings, so we drop them.

    Genuine fields and methods are left untouched. (Inherited members are
    excluded separately via ``inherited-members: False`` below — note that these
    generated members are defined on the model class itself, not inherited, which
    is why they need explicit skipping.)
    """
    if name == "DoesNotExist":
        return True
    if isinstance(obj, pw.ForeignKeyField) and name != obj.name:
        return True
    if isinstance(obj, pw.BackrefAccessor):
        return True
    return skip


def setup(app):
    app.connect("autodoc-skip-member", skip_peewee_internals)
    app.connect("builder-inited", vignettes.generate_custom_stubs)
