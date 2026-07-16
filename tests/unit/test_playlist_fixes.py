"""Playlist download fixes: blind subtitle selection, non-strict finalize,
and error formatting for playlist summary panels."""

from pathlib import Path
from unittest.mock import patch

import pytest

from vidsmith.cli.executor import (
    _best_video_job,
    _blind_subtitle_selection,
    _finalize_download,
    _format_item_error,
)
from vidsmith.downloader.job import DownloadJob, DownloadMediaType, SubtitleMode
from vidsmith.downloader.validators.models import (
    DownloadValidationResult,
    ValidationErrorCode,
)
from vidsmith.models.media import AnalysisResult, MediaType
from vidsmith.providers.results import DownloadResult, DownloadResultStatus
from vidsmith.utils.exceptions import DownloadError


def _analysis() -> AnalysisResult:
    return AnalysisResult(
        url="https://youtube.com/playlist?list=abc",
        media_type=MediaType.PLAYLIST,
    )


def _job() -> DownloadJob:
    return DownloadJob(
        url="https://youtube.com/watch?v=123",
        media_type=DownloadMediaType.VIDEO,
        output_dir=Path("/tmp"),
    )


def _dl_result() -> DownloadResult:
    return DownloadResult(
        job_id="test",
        url="https://youtube.com/watch?v=123",
        status=DownloadResultStatus.COMPLETED,
        output_dir=Path("/tmp"),
    )


def test_blind_selection_requests_supported_set() -> None:
    selection = _blind_subtitle_selection()
    assert selection.codes == ["te", "hi", "ta", "en"]
    assert selection.requested == ["te", "hi", "ta", "en"]


def test_best_video_job_playlist_item_gets_subtitles() -> None:
    # Playlist items (url passed) have no per-item caption data; the full
    # supported set is requested blindly instead of disabling subtitles.
    job = _best_video_job(_analysis(), Path("/tmp"), url="https://youtube.com/watch?v=xyz")
    assert job.subtitle_mode == SubtitleMode.BOTH
    assert job.subtitle_languages == ["te", "hi", "ta", "en"]
    assert job.subtitle_requested_languages == ["te", "hi", "ta", "en"]


def _failed_validation(code: str) -> DownloadValidationResult:
    validation = DownloadValidationResult()
    validation.fail(code, f"Validation failed: {code}")
    return validation


@pytest.mark.parametrize(
    "code",
    [ValidationErrorCode.THUMBNAIL_NOT_EMBEDDED, ValidationErrorCode.SUBTITLE_MISSING],
)
def test_finalize_non_strict_returns_on_embed_failures(code: str) -> None:
    with patch("vidsmith.cli.executor.validate_download", return_value=_failed_validation(code)):
        validation = _finalize_download(_job(), _dl_result(), strict=False)
    assert validation.success is False
    assert validation.error_code == code


@pytest.mark.parametrize("code", [ValidationErrorCode.FILE_MISSING, ValidationErrorCode.FILE_EMPTY])
def test_finalize_non_strict_still_raises_on_missing_media(code: str) -> None:
    with (
        patch("vidsmith.cli.executor.validate_download", return_value=_failed_validation(code)),
        pytest.raises(DownloadError),
    ):
        _finalize_download(_job(), _dl_result(), strict=False)


def test_finalize_strict_raises_on_any_failure() -> None:
    validation = _failed_validation(ValidationErrorCode.THUMBNAIL_NOT_EMBEDDED)
    with (
        patch("vidsmith.cli.executor.validate_download", return_value=validation),
        pytest.raises(DownloadError),
    ):
        _finalize_download(_job(), _dl_result())


def test_format_item_error_strips_retry_prefix() -> None:
    msg = "YouTube video download failed after 3 attempts: ERROR: [youtube] QMx6abc: Video unavailable"
    assert _format_item_error(msg) == "ERROR: [youtube] QMx6abc: Video unavailable"


def test_format_item_error_truncates_and_collapses() -> None:
    msg = "line one\nline two   with   spaces"
    assert _format_item_error(msg) == "line one line two with spaces"
    long = "x" * 500
    assert len(_format_item_error(long)) == 160
    assert _format_item_error(long).endswith("…")


def test_format_item_error_empty_fallback() -> None:
    assert _format_item_error("   ") == "Unknown error"
