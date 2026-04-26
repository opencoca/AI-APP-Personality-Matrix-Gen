help:
	@echo "=================================================="
	@echo "     $(OWNER)/$(PROJECT_NAME) by Startr.Cloud"
	@echo "=================================================="
	@echo ""
	@echo "Available make commands:"
	@echo ""
	@LC_ALL=C $(MAKE) -pRrq -f $(firstword $(MAKEFILE_LIST)) : 2>/dev/null | \
		awk -v RS= -F: '/(^|\n)# Files(\n|$$)/,/(^|\n)# Finished Make data base/ { \
		if ($$1 !~ "^[#.]") {print $$1}}' | \
		sort | \
		grep -E -v -e '^[^[:alnum:]]' -e '^$$@$$'
	@echo ""

# ── Dynamic variables from git ─────────────────────────────────────────────────
PROJECTPATH  := $(shell git rev-parse --show-toplevel)
PROJECT      := $(shell echo $$(basename $(PROJECTPATH)) | tr '[:upper:]' '[:lower:]')
FULL_BRANCH  := $(shell git rev-parse --abbrev-ref HEAD)
BRANCH       := $(shell echo $(FULL_BRANCH) | sed 's/.*\///' | tr '[:upper:]' '[:lower:]')
TAG          := $(shell git describe --always --tags 2>/dev/null || echo "untagged")
REMOTE_URL   := $(shell git config --get remote.origin.url 2>/dev/null || echo "unknown/unknown")
OWNER        := $(shell echo $(REMOTE_URL) | sed -E 's|.*[:/]([^/]+)/[^/]+(.git)?$$|\1|')
PROJECT_NAME := $(shell echo $(REMOTE_URL) | sed -E 's|.*[:/][^/]+/([^/]+)(.git)?$$|\1|' | sed 's/\.git$$//')

-include .env

# ── Python / UV ────────────────────────────────────────────────────────────────
UV   := uv
VENV := .venv
PKG  := yt_analyst

setup:
	$(UV) venv $(VENV)
	$(UV) pip install -e ".[dev]"
	@echo ""
	@echo "Setup complete. Run: uv run yt-analyst --help"

dev_run:
	$(UV) run yt-analyst $(ARGS)

test:
	$(UV) run pytest tests/ -q

test_verbose:
	$(UV) run pytest tests/ -v

test_coverage:
	$(UV) run pytest tests/ --cov=$(PKG) --cov-report=term-missing

lint:
	$(UV) run ruff check $(PKG)/ scripts/

format:
	$(UV) run ruff format $(PKG)/ scripts/

# ── Release ────────────────────────────────────────────────────────────────────
# Usage: make release VERSION=0.2.0
release:
	@[ -n "$(VERSION)" ] || (echo "Usage: make release VERSION=x.y.z"; exit 1)
	sed -i.bak 's/__version__ = ".*"/__version__ = "$(VERSION)"/' $(PKG)/__init__.py && rm -f $(PKG)/__init__.py.bak
	sed -i.bak 's/^version = ".*"/version = "$(VERSION)"/' pyproject.toml && rm -f pyproject.toml.bak
	@echo "Version bumped to $(VERSION)"
	@echo "Next: git add $(PKG)/__init__.py pyproject.toml && git commit -m 'Release: v$(VERSION)' && git tag v$(VERSION)"
	@echo "Then: git push && git push --tags"

# ── Utilities ──────────────────────────────────────────────────────────────────
show_vars:
	@echo "=== Dynamic Variables ==="
	@echo "PROJECTPATH  = $(PROJECTPATH)"
	@echo "PROJECT      = $(PROJECT)"
	@echo "OWNER        = $(OWNER)"
	@echo "PROJECT_NAME = $(PROJECT_NAME)"
	@echo "FULL_BRANCH  = $(FULL_BRANCH)"
	@echo "BRANCH       = $(BRANCH)"
	@echo "TAG          = $(TAG)"
	@echo "REMOTE_URL   = $(REMOTE_URL)"
	@echo ""

.PHONY: help setup dev_run test test_verbose test_coverage lint format release show_vars
