import json
from pathlib import Path
from unittest import mock

import pytest

from vidsmith.settings import AppSettings
from vidsmith.settings.store import (
    default_download_dir,
    load_settings,
    save_settings,
    settings_path,
)


@pytest.fixture
def mock_settings_dir(tmp_path: Path):
    # Isolate BOTH the new dir and the legacy (pre-rename) location, so a real
    # MediaForge settings file on the developer's machine can't leak in via
    # the one-time migration.
    legacy = tmp_path / "legacy" / "settings.json"
    with (
        mock.patch("vidsmith.settings.store.settings_dir", return_value=tmp_path),
        mock.patch("vidsmith.settings.store._legacy_settings_path", return_value=legacy),
    ):
        yield tmp_path


def test_missing_settings(mock_settings_dir: Path):
    settings = load_settings()
    assert settings.default_container == "mp4"  # Default value
    assert not settings_path().exists()


def test_legacy_mediaforge_settings_migrated(mock_settings_dir: Path):
    """A pre-rename MediaForge settings file is copied on first load."""
    from vidsmith.settings.store import _legacy_settings_path

    legacy = _legacy_settings_path()
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_text(
        json.dumps({"version": 1, "settings": {"default_container": "mkv"}}),
        encoding="utf-8",
    )

    loaded = load_settings()
    assert loaded.default_container == "mkv"
    # Copied, not moved — the legacy file stays as a fallback.
    assert legacy.exists()
    assert settings_path().exists()


def test_migration_never_overwrites_existing_settings(mock_settings_dir: Path):
    """Once a VidSmith settings file exists, the legacy file is ignored."""
    from vidsmith.settings.store import _legacy_settings_path

    legacy = _legacy_settings_path()
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_text(json.dumps({"default_container": "webm"}), encoding="utf-8")

    save_settings(AppSettings(default_container="mkv"))
    loaded = load_settings()
    assert loaded.default_container == "mkv"


def test_save_and_load_settings(mock_settings_dir: Path):
    s = AppSettings(default_container="mkv", subtitle_delay_seconds=999)
    save_settings(s)

    assert settings_path().exists()
    data = json.loads(settings_path().read_text())
    assert data["version"] == 1
    assert data["settings"]["default_container"] == "mkv"
    assert data["settings"]["subtitle_delay_seconds"] == 999

    loaded = load_settings()
    assert loaded.default_container == "mkv"
    assert loaded.subtitle_delay_seconds == 999


def test_cookies_from_browser_round_trip(mock_settings_dir: Path):
    s = AppSettings(cookies_from_browser="chrome")
    save_settings(s)

    data = json.loads(settings_path().read_text())
    assert data["settings"]["cookies_from_browser"] == "chrome"
    assert load_settings().cookies_from_browser == "chrome"


def test_settings_file_without_cookies_key_defaults_off(mock_settings_dir: Path):
    """Files written before the cookies feature load with it disabled."""
    sp = settings_path()
    sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_text(json.dumps({"version": 1, "settings": {"default_container": "mkv"}}))

    loaded = load_settings()
    assert loaded.cookies_from_browser == ""
    assert loaded.default_container == "mkv"


def test_corrupt_settings(mock_settings_dir: Path):
    sp = settings_path()
    sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_text("{ corrupt json")

    loaded = load_settings()
    assert loaded.default_container == "mp4"  # Returns default

    backup_path = sp.with_suffix(sp.suffix + ".bak")
    assert backup_path.exists()
    assert backup_path.read_text() == "{ corrupt json"
    assert not sp.exists()


def test_legacy_flat_format_still_loads(mock_settings_dir: Path):
    """Pre-versioning files were a flat dict; they must load unchanged."""
    sp = settings_path()
    sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_text(json.dumps({"default_container": "webm", "max_concurrency": 5}))

    loaded = load_settings()
    assert loaded.default_container == "webm"
    assert loaded.max_concurrency == 5
    # Unknown-format file must NOT be treated as corrupt.
    assert sp.exists()
    assert not sp.with_suffix(sp.suffix + ".bak").exists()


def test_legacy_file_upgraded_on_next_save(mock_settings_dir: Path):
    sp = settings_path()
    sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_text(json.dumps({"default_container": "webm"}))

    loaded = load_settings()
    save_settings(loaded)

    data = json.loads(sp.read_text())
    assert data["version"] == 1
    assert data["settings"]["default_container"] == "webm"


def test_versioned_with_bad_payload_recovers(mock_settings_dir: Path):
    sp = settings_path()
    sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_text(json.dumps({"version": 1, "settings": "not-a-dict"}))

    loaded = load_settings()
    assert loaded.default_container == "mp4"
    assert sp.with_suffix(sp.suffix + ".bak").exists()


def test_default_download_dir(mock_settings_dir: Path):
    import vidsmith.settings.store as store

    with mock.patch.object(store, "_current", AppSettings()):
        assert default_download_dir() == "~/Downloads"
    with mock.patch.object(store, "_current", AppSettings(default_output_directory="D:/Media")):
        assert default_download_dir() == "D:/Media"


def test_execute_settings_round_trip(mock_settings_dir: Path):
    """execute_settings maps wizard state → AppSettings → disk → shared instance."""
    from vidsmith.cli.executor import execute_settings
    from vidsmith.cli.wizard.base import WizardState
    from vidsmith.settings.store import current_settings

    state = WizardState(
        {
            "default_output_directory": "D:/Media",
            "default_container": "mkv",
            "default_quality": "720",
            "default_audio_format": "flac",
            "default_audio_quality": "320k",
            "subtitle_delay_mode": "custom",
            "subtitle_delay_custom": 60,
            "cleanup_enabled": False,
            "keep_temp_files": True,
            "node_path_override": "",
            "ffmpeg_path_override": "",
            "max_concurrency": 4,
        }
    )
    execute_settings(state)

    # Shared instance updated in-process…
    s = current_settings()
    assert s.default_container == "mkv"
    assert s.cleanup_enabled is False
    assert s.keep_temp_files is True

    # …and the same values survive a fresh load from disk.
    loaded = load_settings()
    assert loaded.default_output_directory == "D:/Media"
    assert loaded.default_quality == "720"
    assert loaded.default_audio_format == "flac"
    assert loaded.default_audio_quality == "320k"
    assert loaded.subtitle_delay_seconds == 60
    assert loaded.max_concurrency == 4
