import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

DEFAULTS = {
    "gemini_api_key": "",
    "anki_connect_url": "http://localhost:8765",
}


def _load() -> dict:
    if os.path.isfile(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            return {**DEFAULTS, **json.load(f)}
    return {**DEFAULTS}


def _save(cfg: dict):
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)


def get_all() -> dict:
    """Return config with the API key masked."""
    cfg = _load()
    key = cfg.get("gemini_api_key", "")
    cfg["gemini_api_key_set"] = bool(key)
    cfg["gemini_api_key"] = ""
    return cfg


def update(values: dict):
    """Merge provided values into config. Empty gemini_api_key means keep existing."""
    cfg = _load()
    if "anki_connect_url" in values:
        cfg["anki_connect_url"] = values["anki_connect_url"]
    if values.get("gemini_api_key"):
        cfg["gemini_api_key"] = values["gemini_api_key"]
    _save(cfg)


def get_gemini_api_key() -> str:
    """Return the Gemini API key (config file, then env var fallback)."""
    key = _load().get("gemini_api_key", "")
    return key or os.environ.get("GEMINI_API_KEY", "")


def get_anki_connect_url() -> str:
    """Return the AnkiConnect URL (config file, then env var fallback)."""
    url = _load().get("anki_connect_url", "")
    return url or os.environ.get("ANKI_CONNECT_URL", DEFAULTS["anki_connect_url"])
