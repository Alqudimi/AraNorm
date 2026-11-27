# AraNorm development helpers
# Usage: make <target>

PYTHON       := python
SRC          := src
TESTS        := tests
SCRIPTS      := scripts

.PHONY: help install dev-install test test-fast test-cov server-contracts streaming-contracts plugin-contracts installed-smoke lint format format-check type-check verify benchmark benchmark-quick clean all

help:          ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?##' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

install:       ## Install the package (editable)
	pip install -e .

dev-install:   ## Install package + dev/quality extras
	pip install -e ".[dev,quality]"

test:          ## Run all tests
	$(PYTHON) -m pytest $(TESTS) -v

test-fast:     ## Run tests without verbose output
	$(PYTHON) -m pytest $(TESTS) -q

test-cov:      ## Run tests with coverage report
	$(PYTHON) -m pytest $(TESTS) --cov=$(SRC) --cov-report=term-missing -q

server-contracts: ## Run runtime, HTTP, and serve CLI contract tests
	$(PYTHON) -m pytest $(TESTS)/test_runtime_contracts.py $(TESTS)/test_server_contracts.py $(TESTS)/test_cli_round8.py -q

streaming-contracts: ## Run resumable streaming, CLI, and HTTP contract tests
	$(PYTHON) -m pytest $(TESTS)/test_streaming_session_round10.py $(TESTS)/test_cli_round10.py $(TESTS)/test_server_streaming_round10.py -q

plugin-contracts: ## Run installed-style processor entry-point contracts
	$(PYTHON) -m pytest $(TESTS)/test_plugin_installation_round8.py -q

installed-smoke: ## Build and validate wheel and sdist outside the source tree
	$(PYTHON) -m pytest $(TESTS)/test_installed_smoke.py -q

lint:          ## Run flake8 linter
	flake8 $(SRC) $(TESTS) --max-line-length=120 --extend-ignore=E203,W503

format:        ## Auto-format with black
	black $(SRC) $(TESTS) $(SCRIPTS) --line-length=120

format-check:  ## Check formatting without changing files
	black --check $(SRC) $(TESTS) $(SCRIPTS) --line-length=120

type-check:    ## Run mypy type checker
	mypy $(SRC) --ignore-missing-imports

benchmark:     ## Run the full pipeline benchmark
	$(PYTHON) $(SCRIPTS)/benchmark.py

benchmark-quick: ## Quick benchmark (100 texts only)
	$(PYTHON) $(SCRIPTS)/benchmark.py --quick

clean:         ## Remove build artefacts and caches
	rm -rf build dist *.egg-info src/*.egg-info
	find . -type d -name __pycache__ | xargs rm -rf
	find . -name "*.pyc" -delete
	find . -name ".mypy_cache" -type d | xargs rm -rf
	find . -name ".pytest_cache" -type d | xargs rm -rf

verify: format-check lint type-check test  ## Run the complete non-mutating quality gate

all: verify  ## Run the complete quality gate
