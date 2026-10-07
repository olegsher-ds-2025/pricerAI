import json
import re
import urllib.request

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


def parse(data: dict) -> dict[str, list[dict]]:
    by_provider: dict[str, list[dict]] = {name: [] for name in PROVIDERS.values()}
    for key, entry in data.items():
        provider = PROVIDERS.get(entry.get("litellm_provider"))
        if provider and entry.get("mode") == "chat":
            by_provider[provider] += rows_for(key, entry, provider)
    return by_provider


def fetch() -> dict[str, list[dict]]:
    raw = urllib.request.urlopen(LITELLM_URL, timeout=60).read()
    return parse(json.loads(raw))
