# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "FlexEval"
copyright = "2025, Digital Harbor Foundation"
author = "S. Thomas Christie, Baptiste Moreau-Pernet, Zachary Levonian, Anna Rafferty, Terry Yu Tian"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = []

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
    }
}
html_favicon = "_static/flexeval_favicon.svg"
