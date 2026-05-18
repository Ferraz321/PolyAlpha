import json
import os
import subprocess


_CACHE: dict[str, dict] = {}


def parse_market_semantics(row: dict) -> dict:
    command = os.environ.get("OKTRADER_LLM_MARKET_PARSER")
    if not command:
        return {}
    key = _cache_key(row)
    if key in _CACHE:
        return _CACHE[key]
    payload = {
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
    _CACHE[key] = _clean(parsed)
    return _CACHE[key]


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
