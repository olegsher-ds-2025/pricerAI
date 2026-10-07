# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Status

All planned phases are built and verified locally. Repo `olegsher-ds-2025/pricerAI` is live; Pages serves `master` / root at https://pricerai.sher.biz (HTTPS enforced). Not yet done: installing the collector container on the Pi. The approved design and phased plan live in `~/.claude/plans/analyze-project-requrements-from-lazy-papert.md`.

## Commands

- Run the collector: `python3 -m collector.run [--dry-run]` (stdlib only; exits 1 if any fetch failed or was rejected)
- JS tests: `node --test tests/`
- Serve the site: `python3 -m http.server` (repo root; `index.html` is at the root because Pages publishes from `master` / root)
- Python tests: `uv run --with pytest --with jsonschema python -m pytest -q tests` (single test: append `tests/test_collector.py::test_name`)
- Validate the snapshot: `uv run --with jsonschema python -c "import json,jsonschema; jsonschema.validate(json.load(open('data/current.json')), json.load(open('data/schema.json')))"`

`data/schema.json` defines one row per provider × model × direction × tier × context band, priced in USD per 1M tokens.

## Architecture (from `SystemReq.md` plus decisions made)

PricerAI is a comparison site for AI service prices, hosted as a GitHub Pages web app.

- **Frontend:** vanilla JS ES modules on GitHub Pages (no build step). `index.html` (root) + `site/app.mjs` (DOM) + `site/lib.mjs` (pure logic: pivoting, task costs, history series; the part covered by `tests/lib.test.mjs`). Chart.js loads from cdnjs. Four tabs: token prices, history, special services, cost per task.
- **Collector:** Python, runs daily in a container on the Raspberry Pi (`10.0.0.100`). It pulls prices, validates them, then commits and pushes to this repo. `SystemReq.md` says `10.0.0.20`, but that is the Jetson. The Pi is the intended host.
- **Data sources (hybrid):** machine-readable sources first (e.g. LiteLLM price JSON, OpenRouter API), per-provider pricing-page scraping for gaps, and hand-maintained YAML as the last fallback.
- **Storage:** the git repo. `data/current.json` holds the latest snapshot, `data/history/<provider>.jsonl` is append-only, and commits are the audit trail.
- **Units:** store USD per 1M tokens; the UI scales to the 1B view required by the spec.
- **Task pricing:** `data/tasks.json` (JSON, not YAML, so the browser needs no parser) holds task profiles as a service type plus a usage list (e.g. a book = 10k input + 130k output tokens). A model is ranked only if it has every priced direction the task needs. Task prices are derived from collected prices, never entered by hand.
- **Deploy:** `deploy/Dockerfile` + `deploy/run.sh` (pull, collect, commit `data/` if changed, push). Runs once per invocation; the Pi host cron triggers it (see README). Docker daemon on the dev PC could not bind-mount paths under `/tmp` when testing, so test mounts must live under `/mnt/data`.
- **Special services:** `collector/litellm.py` `SPECIAL` maps LiteLLM modes (embedding, image_generation, audio_transcription, audio_speech, video_generation, ocr) to per-unit rows; only base (standard-tier) prices are kept for them.
- **Collector layout:** `collector/litellm.py` is a source adapter returning rows grouped by provider; `validate.reconcile` guards each provider; `run.py` merges into `data/current.json` and appends only changed prices to `data/history/<provider>.jsonl` (full baseline on first run). New sources register in `run.SOURCES`.
- **Failure rule:** a failed or implausible fetch (zero price, large jump) must not overwrite the last good data: a provider fetch returning under 70% of its previous rows is rejected whole, and a row whose price moves more than 5x keeps its old price.

## Features to deliver

1. Price per 1B tokens per provider, covering every permutation (input/output, cached, batch, context tier, model)
2. Price history
3. Prices for special AI services (image, audio, video, embeddings, etc.)
4. Price per basic task (e.g. generate an image, create a book)
