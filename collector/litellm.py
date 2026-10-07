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
LLM_MODES = {"chat", "responses"}
# mode -> (field, service_type, unit, direction, multiplier to the stored unit)
SPECIAL = {
    "embedding": [("input_cost_per_token", "embedding", "1M_tokens", "input", 1_000_000)],
    "image_generation": [("output_cost_per_image", "image", "image", "output", 1)],
    "audio_transcription": [("input_cost_per_second", "audio", "minute", "input", 60)],
    "audio_speech": [("input_cost_per_character", "audio", "1M_characters", "input", 1_000_000)],
    "video_generation": [
        ("output_cost_per_second", "video", "second", "output", 1),
        ("output_cost_per_video_per_second", "video", "second", "output", 1),
    ],
    "ocr": [("ocr_cost_per_page", "other", "page", "input", 1)],
}
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


def special_rows(key: str, entry: dict, provider: str) -> list[dict]:
    rows = {}
    for field, service_type, unit, direction, scale in SPECIAL.get(entry.get("mode"), []):
        value = entry.get(field)
        if not value:
            continue
        rows[(service_type, unit, direction)] = {
            "provider": provider,
            "model": key.split("/", 1)[-1],
            "service_type": service_type,
            "unit": unit,
            "direction": direction,
            "tier": "standard",
            "context_over": None,
            "price_usd": round(value * scale, 6),
            "source": "api",
            "url": entry.get("source", LITELLM_URL),
        }
    return list(rows.values())


def parse(data: dict) -> dict[str, list[dict]]:
    by_provider: dict[str, list[dict]] = {name: [] for name in PROVIDERS.values()}
    for key, entry in data.items():
        provider = PROVIDERS.get(entry.get("litellm_provider"))
        if not provider:
            continue
        if entry.get("mode") in LLM_MODES:
            by_provider[provider] += rows_for(key, entry, provider)
        else:
            by_provider[provider] += special_rows(key, entry, provider)
    return by_provider


def fetch() -> dict[str, list[dict]]:
    raw = urllib.request.urlopen(LITELLM_URL, timeout=60).read()
    return parse(json.loads(raw))
