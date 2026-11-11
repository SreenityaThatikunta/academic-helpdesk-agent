PY := .venv/bin/python

.PHONY: setup models index web chat test lint eval help

help:  ## List targets
	@grep -E '^[a-z]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-8s %s\n", $$1, $$2}'

setup:  ## Create .venv, install deps, copy .env
	uv venv --python 3.12 .venv
	uv pip install -p .venv -r requirements-dev.txt
	[ -f .env ] || cp .env.example .env

models:  ## Pull the Ollama chat and embedding models (~5.5 GB)
	ollama pull qwen3:8b
	ollama pull nomic-embed-text

index:  ## Build the vector index (~40 s)
	$(PY) -m helpdesk.ingest --reset

web:  ## Web UI at http://localhost:8000
	$(PY) -m helpdesk.web.server

chat:  ## Terminal chat (multi-agent)
	$(PY) -m helpdesk.cli --mode multi

test:  ## Unit tests
	$(PY) -m pytest

lint:  ## Ruff
	$(PY) -m ruff check .

eval:  ## Full evaluation (~80 min) and scoring
	$(PY) eval/run_eval.py
	$(PY) eval/score.py
