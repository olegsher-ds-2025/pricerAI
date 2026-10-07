# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Status

Phases 1-2 done (schema, collector, validation, history). Not yet: frontend, cron/Docker on the Pi, git commit+push from the collector. The approved design and phased plan live in `~/.claude/plans/analyze-project-requrements-from-lazy-papert.md`.

## Commands

- Run the collector: `python3 -m collector.run [--dry-run]` (stdlib only; exits 1 if any fetch failed or was rejected)
- Tests: `uv run --with pytest --with jsonschema python -m pytest -q tests` (single test: append `tests/test_collector.py::test_name`)
- Validate the snapshot: `uv run --with jsonschema python -c "import json,jsonschema; jsonschema.validate(json.load(open('data/current.json')), json.load(open('data/schema.json')))"`

`data/schema.json` defines one row per provider × model × direction × tier × context band, priced in USD per 1M tokens.

## Architecture (from `SystemReq.md` plus decisions made)

PricerAI is a comparison site for AI service prices, hosted as a GitHub Pages web app.

- **Frontend:** vanilla JS on GitHub Pages (no build step, no server runtime). It reads committed JSON and charts it with a CDN library.
- **Collector:** Python, runs daily in a container on the Raspberry Pi (`10.0.0.100`). It pulls prices, validates them, then commits and pushes to this repo. `SystemReq.md` says `10.0.0.20`, but that is the Jetson. The Pi is the intended host.
- **Data sources (hybrid):** machine-readable sources first (e.g. LiteLLM price JSON, OpenRouter API), per-provider pricing-page scraping for gaps, and hand-maintained YAML as the last fallback.
- **Storage:** the git repo. `data/current.json` holds the latest snapshot, `data/history/<provider>.jsonl` is append-only, and commits are the audit trail.
- **Units:** store USD per 1M tokens; the UI scales to the 1B view required by the spec.
- **Task pricing:** `data/tasks.yaml` holds versioned task profiles (e.g. a book as N output tokens). Task prices are derived from collected prices, never entered by hand.
- **Collector layout:** `collector/litellm.py` is a source adapter returning rows grouped by provider; `validate.reconcile` guards each provider; `run.py` merges into `data/current.json` and appends only changed prices to `data/history/<provider>.jsonl` (full baseline on first run). New sources register in `run.SOURCES`.
- **Failure rule:** a failed or implausible fetch (zero price, large jump) must not overwrite the last good data: a provider fetch returning under 70% of its previous rows is rejected whole, and a row whose price moves more than 5x keeps its old price.

## Features to deliver

1. Price per 1B tokens per provider, covering every permutation (input/output, cached, batch, context tier, model)
2. Price history
3. Prices for special AI services (image, audio, video, embeddings, etc.)
4. Price per basic task (e.g. generate an image, create a book)
