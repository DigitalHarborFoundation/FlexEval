
# You can set these variables from the command line, and also
# from the environment for the first two.
SPHINXOPTS    ?=
SPHINXBUILD   ?= uv run sphinx-build
SOURCEDIR     = docs
BUILDDIR      = build

.PHONY: dochelp docautobuild docclean unittest Makefile

# Put it first so that "make" without argument is like "make dochelp".
dochelp:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

docautobuild:
	@uv run sphinx-autobuild "$(SOURCEDIR)" "$(BUILDDIR)"

docclean:
	@echo "Cleaning build directory and generated sources..."
	@rm -rf "$(BUILDDIR)" "$(SOURCEDIR)/generated"

# Non-docs targets
unittest:
	@uv run python -m unittest discover -s tests.unit


# Catch-all target: route all unknown targets to Sphinx using the new
# "make mode" option.  $(O) is meant as a shortcut for $(SPHINXOPTS).
%: Makefile
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)
