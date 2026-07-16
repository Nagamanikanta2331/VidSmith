"""Phase B.5: persisted settings must actually drive wizard defaults."""

from pathlib import Path
from unittest import mock

import pytest

import mediaforge.settings.store as store
from mediaforge.cli.wizard.steps import Choice
from mediaforge.settings import AppSettings


@pytest.fixture
def mock_settings_dir(tmp_path: Path):
    with mock.patch("mediaforge.settings.store.settings_dir", return_value=tmp_path):
        yield tmp_path


@pytest.fixture
def saved(mock_settings_dir: Path):
    """Install a distinctive AppSettings as the shared instance."""
    s = AppSettings(
        default_output_directory="D:/Media",
        default_container="mkv",
        default_quality="720",
        default_audio_format="flac",
        default_audio_quality="320k",
        max_concurrency=4,
    )
    with mock.patch.object(store, "_current", s):
        yield s


def _step_by_key(wizard, key: str):
    return next(step for step in wizard.steps if getattr(step, "key", "") == key)


def test_video_wizard_seeds_from_settings(saved: AppSettings):
    from mediaforge.cli.wizard.wizards.video import build_video_wizard

    wizard = build_video_wizard()
    assert _step_by_key(wizard, "output_dir")._default == "D:/Media"

    fmt = _step_by_key(wizard, "format")
    choices = [Choice("MP4", "mp4"), Choice("MKV", "mkv"), Choice("WebM", "webm")]
    assert fmt._default_index(choices) == 1  # mkv

    quality = _step_by_key(wizard, "quality")
    q_choices = [
        Choice("Best Available", "best"),
        Choice("1080p", "1920x1080"),
        Choice("720p", "1280x720"),
    ]
    assert quality._default_index(q_choices) == 2  # 720


def test_video_wizard_quality_falls_back_to_best(saved: AppSettings):
    from mediaforge.cli.wizard.wizards.video import _default_quality_index

    # Saved quality (720) not offered by this source → Best Available.
    assert _default_quality_index([Choice("Best Available", "best")]) == 0


def test_audio_wizard_seeds_from_settings(saved: AppSettings):
    from mediaforge.cli.wizard.wizards.audio import _FORMAT_CHOICES, build_audio_wizard

    wizard = build_audio_wizard()
    assert _step_by_key(wizard, "output_dir")._default == "D:/Media"

    fmt = _step_by_key(wizard, "audio_format")
    idx = fmt._default_index(_FORMAT_CHOICES)
    assert _FORMAT_CHOICES[idx].value == "flac"


def test_playlist_wizard_seeds_from_settings(saved: AppSettings):
    from mediaforge.cli.wizard.wizards.playlist import (
        _QUALITY_CHOICES,
        build_playlist_wizard,
    )

    wizard = build_playlist_wizard()
    assert _step_by_key(wizard, "output_dir")._default == "D:/Media"
    assert _step_by_key(wizard, "concurrency")._default == 4

    quality = _step_by_key(wizard, "quality")
    idx = quality._default_index(_QUALITY_CHOICES)
    assert _QUALITY_CHOICES[idx].value == "720"


def test_playlist_concurrency_clamped_to_step_max(mock_settings_dir: Path):
    s = AppSettings(max_concurrency=8)  # settings allow up to 8; step caps at 5
    with mock.patch.object(store, "_current", s):
        from mediaforge.cli.wizard.wizards.playlist import build_playlist_wizard

        wizard = build_playlist_wizard()
        assert _step_by_key(wizard, "concurrency")._default == 5


def test_transcript_wizard_seeds_output_dir(saved: AppSettings):
    from mediaforge.cli.wizard.wizards.transcript import build_transcript_wizard

    wizard = build_transcript_wizard()
    assert _step_by_key(wizard, "output_dir")._default == "D:/Media"


def test_settings_wizard_seeds_from_saved_values(saved: AppSettings):
    from mediaforge.cli.wizard.wizards.settings import (
        _CONTAINER_CHOICES,
        build_settings_wizard,
    )

    wizard = build_settings_wizard()
    assert _step_by_key(wizard, "default_output_directory")._default == "D:/Media"
    container = _step_by_key(wizard, "default_container")
    assert _CONTAINER_CHOICES[container._default_index].value == "mkv"


def test_choice_step_callable_default_out_of_range_is_safe():
    """A callable default returning an out-of-range index falls back to 0."""
    from mediaforge.cli.wizard.base import WizardState
    from mediaforge.cli.wizard.steps.choice import ChoiceStep

    step = ChoiceStep(
        key="x",
        title="X",
        choices=[Choice("A", "a")],
        default_index=lambda choices: 99,
    )
    step._choices = [Choice("A", "a")]
    assert step._resolve_current(WizardState()) == 0
