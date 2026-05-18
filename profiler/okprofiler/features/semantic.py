import json
import os
import subprocess

from ..llm import complete_json


_CACHE: dict[str, dict] = {}


def parse_market_semantics(row: dict) -> dict:
    key = _cache_key(row)
    if key in _CACHE:
        return _CACHE[key]
    payload = _payload(row)
    parsed = _parse_with_command(payload) or _parse_with_provider(payload)
    _CACHE[key] = _clean(parsed)
    return _CACHE[key]


def _payload(row: dict) -> dict:
    return {
        "instruction": (
            "Parse this Polymarket market into normalized numeric factors. "
            "Return JSON only. Use null when unknown."
        ),
        "schema": {
            "is_weather_market": "bool|null",
            "weather_city": "string|null",
            "weather_event_date": "YYYY-MM-DD|null",
            "temperature_low_f": "number|null",
            "temperature_high_f": "number|null",
            "temperature_bucket_type": "between|higher|below|null",
        },
        "market": {
            "event_slug": row.get("event_slug"),
            "market_slug": row.get("market_slug"),
            "title": row.get("title"),
            "outcome": row.get("outcome"),
        },
    }


def _parse_with_command(payload: dict) -> dict:
    command = os.environ.get("OKTRADER_LLM_MARKET_PARSER")
    if not command:
        return {}
    try:
        proc = subprocess.run(
            command,
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            shell=True,
            timeout=30,
            check=False,
        )
        parsed = json.loads(proc.stdout) if proc.returncode == 0 and proc.stdout.strip() else {}
    except Exception:
        parsed = {}
    return parsed


def _parse_with_provider(payload: dict) -> dict:
    return complete_json(
        system=(
            "You are a strict market semantics parser. Return only compact JSON "
            "matching the requested schema. Do not add explanations."
        ),
        payload=payload,
    )


def _cache_key(row: dict) -> str:
    return "|".join(str(row.get(column) or "") for column in ["event_slug", "market_slug", "title", "outcome"])


def _clean(parsed: dict) -> dict:
    allowed = {
        "is_weather_market",
        "weather_city",
        "weather_event_date",
        "temperature_low_f",
        "temperature_high_f",
        "temperature_bucket_type",
    }
    return {key: parsed.get(key) for key in allowed if key in parsed}
