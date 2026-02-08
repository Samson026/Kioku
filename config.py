import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

DEFAULTS = {
    "anki_connect_url": "http://172.20.144.1:8765",
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
    """Return all stored app config values."""
    return _load()


def update(values: dict):
    """Merge provided values into config."""
    cfg = _load()
    if "anki_connect_url" in values:
        cfg["anki_connect_url"] = values["anki_connect_url"]
    _save(cfg)


def get_anki_connect_url() -> str:
    """Return the AnkiConnect URL (config file, then env var fallback)."""
    url = _load().get("anki_connect_url", "")
    return url or os.environ.get("ANKI_CONNECT_URL", DEFAULTS["anki_connect_url"])
