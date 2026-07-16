"""Persistent settings store: load/save ``AppSettings`` as JSON on disk.

Stdlib-only (``json`` + ``pathlib`` + ``os``). One file per user under the
platform config directory. Loading never raises: a missing file yields
defaults, a corrupt file is backed up and defaults are returned.
"""

from __future__ import annotations

import json
import os
from dataclasses import fields
from pathlib import Path
from typing import Any

from mediaforge.settings import AppSettings
from mediaforge.utils.console import err_console

_APP_DIR_NAME = "MediaForge"
_FILE_NAME = "settings.json"

# Version of the on-disk JSON document: {"version": N, "settings": {...}}.
# Files written before versioning was introduced are flat dicts and are still
# read transparently (see load_settings).
_SCHEMA_VERSION = 1

# Fields serialized to JSON. ``default_output_dir`` (a Path) is excluded — the
# Phase B ``default_output_directory`` string supersedes it for persistence.
_PERSISTED = (
    "default_quality",
    "default_audio_format",
    "default_audio_quality",
    "max_concurrency",
    "default_output_directory",
    "default_container",
    "subtitle_delay_seconds",
    "cleanup_enabled",
    "keep_temp_files",
    "node_path_override",
    "ffmpeg_path_override",
    "debug_logging",
)

# Cached process-wide instance shared by the provider, cleanup, and wizard.
_current: AppSettings | None = None


def settings_dir() -> Path:
    """Platform config directory for MediaForge."""
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / _APP_DIR_NAME
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / _APP_DIR_NAME.lower()


def settings_path() -> Path:
    return settings_dir() / _FILE_NAME


def _coerce(name: str, raw: Any, default: Any) -> Any:
    """Best-effort coercion of a JSON value to the default's type."""
    if isinstance(default, bool):
        if isinstance(raw, bool):
            return raw
        raise ValueError(f"{name}: expected bool")
    if isinstance(default, int):
        return int(raw)
    if isinstance(default, str):
        return str(raw)
    return raw


def _from_dict(data: dict[str, Any]) -> AppSettings:
    settings = AppSettings()
    defaults = {f.name: getattr(settings, f.name) for f in fields(AppSettings)}
    for key in _PERSISTED:
        if key in data:
            setattr(settings, key, _coerce(key, data[key], defaults[key]))
    return settings


def _to_dict(settings: AppSettings) -> dict[str, Any]:
    return {key: getattr(settings, key) for key in _PERSISTED}


def load_settings() -> AppSettings:
    """Load settings from disk, falling back to defaults.

    Missing file → defaults (no file created). Corrupt/invalid file → back it
    up to ``settings.json.bak``, warn, and return defaults. Never raises.

    Accepts both the versioned document ``{"version": 1, "settings": {...}}``
    and the legacy flat dict written before versioning existed.
    """
    path = settings_path()
    if not path.exists():
        return AppSettings()

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("settings root is not an object")
        if "version" in data:
            payload = data.get("settings")
            if not isinstance(payload, dict):
                raise ValueError("versioned settings payload is not an object")
        else:
            payload = data  # legacy flat format
        return _from_dict(payload)
    except (json.JSONDecodeError, ValueError, OSError, TypeError) as exc:
        _backup_corrupt(path, exc)
        return AppSettings()


def _backup_corrupt(path: Path, exc: Exception) -> None:
    backup = path.with_suffix(path.suffix + ".bak")
    try:
        path.replace(backup)
        note = f" Backed up to {backup.name}."
    except OSError:
        note = ""
    err_console.print(f"[warning]Could not read settings ({exc}); using defaults.{note}[/]")


def save_settings(settings: AppSettings) -> None:
    """Atomically write settings to disk, creating the config dir if needed."""
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    document = {"version": _SCHEMA_VERSION, "settings": _to_dict(settings)}
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(document, indent=2), encoding="utf-8")
    os.replace(tmp, path)
    global _current
    _current = settings


def current_settings() -> AppSettings:
    """Return the shared settings instance, loading from disk on first use."""
    global _current
    if _current is None:
        _current = load_settings()
    return _current


def reload_settings() -> AppSettings:
    """Force a reload from disk into the shared instance."""
    global _current
    _current = load_settings()
    return _current


def set_current(settings: AppSettings) -> None:
    """Replace the shared instance (used after an in-memory edit + save)."""
    global _current
    _current = settings


def default_download_dir() -> str:
    """The user's configured default save location, or ``~/Downloads``."""
    return current_settings().default_output_directory or "~/Downloads"
