"""Playlist download fixes: blind subtitle selection, non-strict finalize,
and error formatting for playlist summary panels."""

from pathlib import Path
from unittest.mock import patch

import pytest

from vidsmith.cli.executor import (
    _best_video_job,
    _blind_subtitle_selection,
    _classify_unavailable,
    _finalize_download,
    _format_item_error,
    _skipped_summary,
)
from vidsmith.downloader.job import DownloadJob, DownloadMediaType, SubtitleMode
from vidsmith.downloader.validators.models import (
    DownloadValidationResult,
    ValidationErrorCode,
)
from vidsmith.models.media import AnalysisResult, MediaType
from vidsmith.playlist.models import OrchestrationStatus
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
    with (
        patch("vidsmith.cli.executor.validate_download", return_value=_failed_validation(code)),
        patch("vidsmith.downloader.cleanup.cleanup_job_artifacts") as mock_cleanup,
    ):
        validation = _finalize_download(_job(), _dl_result(), strict=False)
    assert validation.success is False
    assert validation.error_code == code
    mock_cleanup.assert_called_once()


def test_retry_rate_limited_subtitles_bypassed_for_video_jobs() -> None:
    from vidsmith.downloader.job import DownloadJob, DownloadMediaType
    from vidsmith.providers.youtube import YouTubeProvider, _SubtitleLogger

    provider = YouTubeProvider()
    job = DownloadJob(
        url="https://youtube.com/watch?v=123",
        media_type=DownloadMediaType.VIDEO,
        output_dir=Path("/tmp"),
    )
    logger = _SubtitleLogger()
    logger.subtitle_failures = {"en": "HTTP Error 429: Too Many Requests"}
    # Must immediately return empty list without any sleeping
    result = provider._retry_rate_limited_subtitles(job, job.url, {}, logger, None)
    assert result == []


def test_embed_thumbnail_postprocessor_does_not_keep_transient_sidecar() -> None:
    from vidsmith.downloader.job import DownloadJob, DownloadMediaType, ThumbnailMode
    from vidsmith.providers.youtube import YouTubeProvider

    provider = YouTubeProvider()
    job = DownloadJob(
        url="https://youtube.com/watch?v=123",
        media_type=DownloadMediaType.VIDEO,
        thumbnail_mode=ThumbnailMode.EMBED,
        video_format="mp4",
        output_dir=Path("/tmp"),
    )
    pps = provider._postprocessors(job)
    embed_pp = next((p for p in pps if p.get("key") == "EmbedThumbnail"), None)
    assert embed_pp is not None
    assert embed_pp["already_have_thumbnail"] is False


def test_all_download_stages_can_be_dispatched() -> None:
    from vidsmith.downloader.progress import DownloadProgress, DownloadStage

    for stage in DownloadStage:
        prog = DownloadProgress(job_id="test", stage=stage)
        assert prog.stage == stage
    # Test backwards-compatible aliases
    assert DownloadStage.PROCESSING_METADATA == DownloadStage.EMBEDDING_METADATA
    assert DownloadStage.PROCESSING_THUMBNAIL == DownloadStage.EMBEDDING_THUMBNAIL




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


# Exact error shapes observed from a real playlist run (2 private, 2 terminated).
@pytest.mark.parametrize(
    ("msg", "expected"),
    [
        (
            "ERROR: [youtube] QMx6FA8gmgU: Private video. Sign in if you've been "
            "granted access to this video. Use --cookies-from-browser or --cookies",
            "private",
        ),
        (
            "ERROR: [youtube] 5h4m0BJ65CU: Video unavailable. This video is no longer "
            "available because the YouTube account associated with this video has been terminated.",
            "deleted",
        ),
        (
            "YouTube video download failed after 3 attempts: ERROR: [youtube] "
            "abc: Video unavailable",
            "deleted",
        ),
        ("ERROR: [youtube] xyz: This video has been removed by the uploader", "deleted"),
    ],
)
def test_classify_unavailable_matches(msg: str, expected: str) -> None:
    assert _classify_unavailable(msg) == expected


@pytest.mark.parametrize(
    "msg",
    [
        "ERROR: unable to download video data: HTTP Error 403: Forbidden",
        "ffmpeg exited with code 1",
        "Validation failed: Thumbnail embedding failed",
        "",
    ],
)
def test_classify_unavailable_ignores_real_failures(msg: str) -> None:
    assert _classify_unavailable(msg) is None


def test_skipped_summary_counts_reasons() -> None:
    assert (
        _skipped_summary(["private", "deleted", "deleted", "private"])
        == "4 skipped: 2 deleted, 2 private"
    )
    assert _skipped_summary(["private"]) == "1 skipped: 1 private"


def test_playlist_subtitles_none_disables_subtitles() -> None:
    from vidsmith.cli.executor import execute_playlist
    from vidsmith.cli.wizard.base import WizardState
    from vidsmith.playlist.models import PlaylistResult

    state = WizardState(
        {
            "output_dir": "/tmp",
            "media_type": "video",
            "quality": "best",
            "item_selection": "all",
            "subtitle_langs": ["none"],
        }
    )
    dummy_result = PlaylistResult(
        job_id="test",
        status=OrchestrationStatus.COMPLETED,
        total_items=0,
        completed=0,
        failed=0,
        skipped=0,
    )
    with (
        patch("vidsmith.playlist.engine.PlaylistEngine.submit", return_value=dummy_result) as mock_submit,
        patch("vidsmith.cli.executor.Prompt.ask", return_value=""),
    ):
        execute_playlist(state, _analysis())
        assert mock_submit.called
        job = mock_submit.call_args[0][0]
        assert job.download_template.subtitle_mode == SubtitleMode.NONE
        assert job.download_template.subtitle_languages == []
        assert job.download_template.subtitle_requested_languages == []


def test_playlist_subtitles_empty_disables_subtitles() -> None:
    from vidsmith.cli.executor import execute_playlist
    from vidsmith.cli.wizard.base import WizardState
    from vidsmith.playlist.models import PlaylistResult

    state = WizardState(
        {
            "output_dir": "/tmp",
            "media_type": "video",
            "quality": "best",
            "item_selection": "all",
            "subtitle_langs": [],
        }
    )
    dummy_result = PlaylistResult(
        job_id="test",
        status=OrchestrationStatus.COMPLETED,
        total_items=0,
        completed=0,
        failed=0,
        skipped=0,
    )
    with (
        patch("vidsmith.playlist.engine.PlaylistEngine.submit", return_value=dummy_result) as mock_submit,
        patch("vidsmith.cli.executor.Prompt.ask", return_value=""),
    ):
        execute_playlist(state, _analysis())
        assert mock_submit.called
        job = mock_submit.call_args[0][0]
        assert job.download_template.subtitle_mode == SubtitleMode.NONE
        assert job.download_template.subtitle_languages == []


def test_playlist_subtitles_custom_does_not_force_english() -> None:
    from vidsmith.cli.executor import execute_playlist
    from vidsmith.cli.wizard.base import WizardState
    from vidsmith.playlist.models import PlaylistResult

    state = WizardState(
        {
            "output_dir": "/tmp",
            "media_type": "video",
            "quality": "best",
            "item_selection": "all",
            "subtitle_langs": ["te"],
        }
    )
    dummy_result = PlaylistResult(
        job_id="test",
        status=OrchestrationStatus.COMPLETED,
        total_items=0,
        completed=0,
        failed=0,
        skipped=0,
    )
    with (
        patch("vidsmith.playlist.engine.PlaylistEngine.submit", return_value=dummy_result) as mock_submit,
        patch("vidsmith.cli.executor.Prompt.ask", return_value=""),
    ):
        execute_playlist(state, _analysis())
        assert mock_submit.called
        job = mock_submit.call_args[0][0]
        assert job.download_template.subtitle_mode == SubtitleMode.BOTH
        assert job.download_template.subtitle_languages == ["te"]
        assert "en" not in job.download_template.subtitle_languages


def test_playlist_thumbnail_mode_propagates_to_template() -> None:
    from vidsmith.cli.executor import execute_playlist
    from vidsmith.cli.wizard.base import WizardState
    from vidsmith.downloader.job import ThumbnailMode
    from vidsmith.playlist.models import PlaylistResult

    state = WizardState(
        {
            "output_dir": "/tmp",
            "media_type": "video",
            "quality": "best",
            "thumbnail_mode": "save",
            "item_selection": "all",
            "subtitle_langs": ["none"],
        }
    )
    dummy_result = PlaylistResult(
        job_id="test",
        status=OrchestrationStatus.COMPLETED,
        total_items=0,
        completed=0,
        failed=0,
        skipped=0,
    )
    with (
        patch("vidsmith.playlist.engine.PlaylistEngine.submit", return_value=dummy_result) as mock_submit,
        patch("vidsmith.cli.executor.Prompt.ask", return_value=""),
    ):
        execute_playlist(state, _analysis())
        assert mock_submit.called
        job = mock_submit.call_args[0][0]
        assert job.download_template.thumbnail_mode == ThumbnailMode.SAVE


