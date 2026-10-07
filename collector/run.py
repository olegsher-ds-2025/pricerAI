import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from collector import litellm
from collector.validate import reconcile, row_key

DATA = Path("data")
SOURCES = {"litellm": litellm.fetch}


def load_current() -> dict[str, list[dict]]:
    path = DATA / "current.json"
    by_provider: dict[str, list[dict]] = {}
    if path.exists():
        for row in json.loads(path.read_text())["rows"]:
            by_provider.setdefault(row["provider"], []).append(row)
    return by_provider


def history_entries(new: list[dict], old: list[dict], observed_at: str) -> list[dict]:
    old_prices = {row_key(r): r["price_usd"] for r in old}
    return [{"observed_at": observed_at, **r} for r in new if old_prices.get(row_key(r)) != r["price_usd"]]


def history_path(provider: str) -> Path:
    return DATA / "history" / f"{provider.lower()}.jsonl"


def append_history(provider: str, entries: list[dict]) -> None:
    if not entries:
        return
    path = history_path(provider)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.writelines(json.dumps(e, separators=(",", ":")) + "\n" for e in entries)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="report changes without writing files")
    args = ap.parse_args()

    observed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    current = load_current()
    published = dict(current)
    failed = False

    for name, fetch in SOURCES.items():
        try:
            fetched = fetch()
        except Exception as exc:
            print(f"{name}: fetch failed: {exc}", file=sys.stderr)
            failed = True
            continue
        for provider, new in fetched.items():
            old = current.get(provider, [])
            rows, issues = reconcile(new, old)
            for issue in issues:
                print(f"{provider}: {issue}", file=sys.stderr)
            failed |= bool(issues)
            baseline = old if history_path(provider).exists() else []
            entries = history_entries(rows, baseline, observed_at)
            print(f"{provider}: {len(rows)} rows, {len(entries)} changed")
            published[provider] = rows
            if not args.dry_run:
                append_history(provider, entries)

    if not args.dry_run:
        all_rows = sorted((r for rows in published.values() for r in rows),
                          key=lambda r: (*row_key(r)[:2], r["direction"], r["tier"], r["context_over"] or 0))
        (DATA / "current.json").write_text(json.dumps({"generated_at": observed_at, "rows": all_rows}, indent=1) + "\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
