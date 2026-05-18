import json
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class LlmConfig:
    provider: str
    base_url: str
    model: str
    auth_token: str
    timeout_secs: int = 45


def complete_json(system: str, payload: dict) -> dict:
    config = load_config()
    if config is None:
        return {}
    if config.provider == "anthropic":
        return _anthropic_json(config, system, payload)
    return {}


def load_config() -> LlmConfig | None:
    provider = os.environ.get("OKTRADER_LLM_PROVIDER", "anthropic").strip().lower()
    if provider in {"", "off", "none", "disabled"}:
        return None
    claude_env = _claude_settings_env()
    base_url = _env("OKTRADER_LLM_BASE_URL", "ANTHROPIC_BASE_URL", claude_env)
    auth_token = _env("OKTRADER_LLM_API_KEY", "ANTHROPIC_AUTH_TOKEN", claude_env)
    model = _env("OKTRADER_LLM_MODEL", "ANTHROPIC_MODEL", claude_env) or "GLM-5.1"
    if not base_url or not auth_token:
        return None
    timeout = int(os.environ.get("OKTRADER_LLM_TIMEOUT_SECS", "45"))
    return LlmConfig(provider=provider, base_url=base_url, model=model, auth_token=auth_token, timeout_secs=timeout)


def _anthropic_json(config: LlmConfig, system: str, payload: dict) -> dict:
    body = {
        "model": config.model,
        "max_tokens": 1000,
        "temperature": 0,
        "system": system,
        "messages": [
            {
                "role": "user",
                "content": json.dumps(payload, ensure_ascii=True),
            }
        ],
    }
    for auth_header in _auth_header_candidates():
        try:
            request = Request(
                _anthropic_messages_url(config.base_url),
                data=json.dumps(body).encode("utf-8"),
                headers=_anthropic_headers(config, auth_header),
                method="POST",
            )
            with urlopen(request, timeout=config.timeout_secs) as response:
                data = json.loads(response.read().decode("utf-8"))
            parsed = _extract_json(_anthropic_text(data))
            if parsed:
                return parsed
        except Exception:
            continue
    return {}


def _anthropic_messages_url(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/v1/messages"):
        return base
    if base.endswith("/v1"):
        return base + "/messages"
    return base + "/v1/messages"


def _anthropic_headers(config: LlmConfig, auth_header: str) -> dict:
    headers = {
        "Content-Type": "application/json",
        "anthropic-version": os.environ.get("ANTHROPIC_VERSION", "2023-06-01"),
    }
    if auth_header.lower() == "authorization":
        headers["Authorization"] = f"Bearer {config.auth_token}"
    else:
        headers[auth_header] = config.auth_token
    return headers


def _auth_header_candidates() -> list[str]:
    configured = os.environ.get("OKTRADER_LLM_AUTH_HEADER")
    if configured:
        return [configured]
    return ["x-api-key", "authorization"]


def _anthropic_text(data: dict) -> str:
    content = data.get("content", [])
    if isinstance(content, list):
        return "\n".join(item.get("text", "") for item in content if isinstance(item, dict))
    return str(content or "")


def _extract_json(text: str) -> dict:
    stripped = text.strip()
    if not stripped:
        return {}
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        stripped = stripped.removeprefix("json").strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end >= start:
        stripped = stripped[start : end + 1]
    try:
        parsed = json.loads(stripped)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _claude_settings_env() -> dict:
    path = Path.home() / ".claude" / "settings.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("env", {})
    except Exception:
        return {}


def _env(primary: str, fallback: str, settings: dict) -> str | None:
    return os.environ.get(primary) or os.environ.get(fallback) or settings.get(fallback)
