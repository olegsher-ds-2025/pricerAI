import json
from pathlib import Path

import jsonschema

from collector.litellm import parse
from collector.validate import reconcile, row_key
from collector.run import history_entries

ENTRY = {
    "litellm_provider": "anthropic", "mode": "chat", "source": "https://example.test/pricing",
    "input_cost_per_token": 3e-06, "output_cost_per_token": 1.5e-05,
    "input_cost_per_token_above_200k_tokens": 6e-06,
    "input_cost_per_token_batches": 1.5e-06, "cache_creation_input_token_cost_above_1hr": 6e-06,
    "max_tokens": 64000,
}


def rows():
    return parse({"claude-x": ENTRY, "other/embed": {"litellm_provider": "openai", "mode": "embedding"}})["Anthropic"]


def test_parse_maps_variants():
    got = {(r["direction"], r["tier"], r["context_over"]): r["price_usd"] for r in rows()}
    assert got == {
        ("input", "standard", None): 3.0,
        ("output", "standard", None): 15.0,
        ("input", "standard", 200000): 6.0,
        ("input", "batch", None): 1.5,
        ("cache_write_1h", "standard", None): 6.0,
    }


def test_parse_skips_unsupported_modes():
    assert parse({"e": {"litellm_provider": "openai", "mode": "moderation", "input_cost_per_token": 1e-7}})["OpenAI"] == []


def test_rows_match_schema():
    schema = json.loads((Path("data") / "schema.json").read_text())
    jsonschema.validate({"generated_at": "2026-01-01T00:00:00+00:00", "rows": rows()}, schema)


def test_reconcile_rejects_shrunk_fetch():
    old = rows()
    out, issues = reconcile(old[:2], old)
    assert out == old and issues


def test_reconcile_rejects_empty_fetch():
    old = rows()
    out, issues = reconcile([], old)
    assert out == old and issues


def test_reconcile_keeps_old_price_on_jump():
    old = rows()
    new = [dict(r) for r in old]
    new[0]["price_usd"] *= 100
    out, issues = reconcile(new, old)
    assert out[0]["price_usd"] == old[0]["price_usd"] and len(issues) == 1


def test_reconcile_accepts_normal_change():
    old = rows()
    new = [dict(r) for r in old]
    new[0]["price_usd"] *= 0.5
    out, issues = reconcile(new, old)
    assert out[0]["price_usd"] == new[0]["price_usd"] and not issues


def test_history_only_records_changes():
    old = rows()
    new = [dict(r) for r in old]
    new[0]["price_usd"] *= 0.5
    entries = history_entries(new, old, "t")
    assert len(entries) == 1 and row_key(entries[0]) == row_key(new[0])
    assert len(history_entries(new, new, "t")) == 0


def test_special_services_and_responses_mode():
    data = {
        "emb": {"litellm_provider": "openai", "mode": "embedding", "input_cost_per_token": 2e-07},
        "img": {"litellm_provider": "openai", "mode": "image_generation", "output_cost_per_image": 0.04},
        "stt": {"litellm_provider": "openai", "mode": "audio_transcription", "input_cost_per_second": 0.0001},
        "vid": {"litellm_provider": "openai", "mode": "video_generation", "output_cost_per_second": 0.1,
                "output_cost_per_video_per_second": 0.1},
        "codex": {"litellm_provider": "openai", "mode": "responses", "input_cost_per_token": 1e-06},
    }
    got = {(r["model"], r["service_type"], r["unit"], r["direction"]): r["price_usd"] for r in parse(data)["OpenAI"]}
    assert got == {
        ("emb", "embedding", "1M_tokens", "input"): 0.2,
        ("img", "image", "image", "output"): 0.04,
        ("stt", "audio", "minute", "input"): 0.006,
        ("vid", "video", "second", "output"): 0.1,
        ("codex", "llm", "1M_tokens", "input"): 1.0,
    }
