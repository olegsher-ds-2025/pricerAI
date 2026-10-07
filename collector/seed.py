import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

LITELLM_URL = "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"
PROVIDERS = {"openai": "OpenAI", "anthropic": "Anthropic", "gemini": "Google", "mistral": "Mistral"}
DIRECTIONS = {
    "input_cost_per_token": "input",
    "output_cost_per_token": "output",
    "cache_read_input_token_cost": "cache_read",
    "cache_creation_input_token_cost": "cache_write",
}
KEY_RE = re.compile(
    r"^(?P<base>input_cost_per_token|output_cost_per_token|cache_read_input_token_cost|cache_creation_input_token_cost)"
    r"(?P<hr>_above_1hr)?(?:_above_(?P<ctx>\d+)k_tokens)?(?:_(?P<tier>batches|priority|flex))?$"
)
TIERS = {"batches": "batch", "priority": "priority", "flex": "flex"}


def rows_for(key: str, entry: dict, provider: str) -> list[dict]:
    model = key.split("/", 1)[-1]
    out = []
    for field, value in entry.items():
        m = KEY_RE.match(field)
        if not m or not value:
            continue
        direction = DIRECTIONS[m["base"]]
        if m["hr"]:
            direction = "cache_write_1h"
        out.append({
            "provider": provider,
            "model": model,
            "service_type": "llm",
            "unit": "1M_tokens",
            "direction": direction,
            "tier": TIERS.get(m["tier"], "standard"),
            "context_over": int(m["ctx"]) * 1000 if m["ctx"] else None,
            "price_usd": round(value * 1_000_000, 6),
            "source": "api",
            "url": entry.get("source", LITELLM_URL),
        })
    return out


def build(data: dict) -> dict:
    rows = []
    for key, entry in data.items():
        provider = PROVIDERS.get(entry.get("litellm_provider"))
        if provider and entry.get("mode") == "chat":
            rows += rows_for(key, entry, provider)
    rows.sort(key=lambda r: (r["provider"], r["model"], r["direction"], r["tier"], r["context_over"] or 0))
    return {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "rows": rows}


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else None
    raw = open(src).read() if src else urllib.request.urlopen(LITELLM_URL, timeout=60).read()
    snapshot = build(json.loads(raw))
    Path("data/current.json").write_text(json.dumps(snapshot, indent=1) + "\n")
    print(f"{len(snapshot['rows'])} rows")
