
# You can set these variables from the command line, and also
# from the environment for the first two.
SPHINXOPTS    ?=
SPHINXBUILD   ?= uv run sphinx-build
SOURCEDIR     = docs
BUILDDIR      = build

.PHONY: dochelp docautobuild docclean unittest get-version set-version Makefile

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

# see: https://hatch.pypa.io/1.13/version/
get-version:
	@uv run hatch version

set-version:
	@if [ -z "$(VERSION)" ]; then \
		echo "VERSION is not set. Usage: make set-version VERSION=x.y.z"; \
		exit 1; \
	fi
	@uv run hatch version "$(VERSION)"

# Catch-all target: route all unknown targets to Sphinx using the new
# "make mode" option.  $(O) is meant as a shortcut for $(SPHINXOPTS).
%: Makefile
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)
