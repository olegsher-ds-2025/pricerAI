# PricerAI

Compares AI API prices across providers: per-token prices (every tier and cache variant), special services (image, audio, video, embeddings, OCR), price history, and the cost of basic tasks.

The site is static. A collector container on the Raspberry Pi pulls prices daily, commits `data/` and pushes; GitHub Pages serves `index.html` straight from `main`.

## Publish

1. The repo is `olegsher-ds-2025/pricerAI` (public, required for free Pages).
2. Settings → Pages → Deploy from branch → `master` / root. The `CNAME` file sets the custom domain (pricerai.sher.biz).

## Collector on the Pi

```sh
git clone git@github.com:<you>/pricerAI.git /opt/pricerai/repo
docker build -f deploy/Dockerfile -t pricerai-collector /opt/pricerai/repo
```

Add the Pi's public key as a write-enabled deploy key on the repo, then schedule the run (crontab of the user that owns the clone):

```cron
17 4 * * * docker run --rm --user $(id -u):$(id -g) -e HOME=/tmp -v /opt/pricerai/repo:/repo -v /opt/pricerai/deploy_key:/key:ro pricerai-collector
```

The job commits once a day, even when only the `generated_at` timestamp moved. The site shows a banner when that timestamp is more than 3 days old, so a dead collector is visible. A rejected fetch makes the run exit non-zero but still pushes whatever was kept.

## Develop

```sh
python3 -m collector.run --dry-run
uv run --with pytest --with jsonschema python -m pytest -q tests
node --test tests/
python3 -m http.server   # then open http://localhost:8000
```

Task profiles (the assumptions behind "cost per task") live in `data/tasks.json`.
