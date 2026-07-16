import json
from pathlib import Path

import pytest

from vidsmith.downloader.cleanup import cleanup_job_artifacts
from vidsmith.downloader.job import (  # type: ignore
    DownloadJob,
    DownloadMediaType,
    MetadataMode,
    SubtitleMode,
    ThumbnailMode,
)
from vidsmith.downloader.validator import validate_download
from vidsmith.providers.results import DownloadResult, DownloadResultStatus

# In a real E2E we'd use YouTubeProvider, but we want a purely isolated cleanup test.
# We will create mock files that represent a completed download, run validation, and then cleanup.
# Then assert that the primary output remains and temporary artifacts are removed.


@pytest.fixture
def temp_output(tmp_path: Path) -> Path:
    return tmp_path


def test_e2e_cleanup_retains_primary_and_removes_temp(temp_output: Path) -> None:
    # 1. Create a mock media file and a mock temporary thumbnail
    media_file = temp_output / "video.mp4"
    temp_thumb = temp_output / "video.webp"

    media_file.write_text("dummy media")
    temp_thumb.write_text("dummy thumb")

    job = DownloadJob(
        url="https://youtube.com/watch?v=123",
        media_type=DownloadMediaType.VIDEO,
        output_dir=temp_output,
        thumbnail_mode=ThumbnailMode.EMBED,
        metadata_mode=MetadataMode.NONE,
        subtitle_mode=SubtitleMode.NONE,
    )

    result = DownloadResult(
        job_id="test",
        url="https://youtube.com/watch?v=123",
        status=DownloadResultStatus.COMPLETED,
        output_dir=temp_output,
        files=[media_file, temp_thumb],
    )

    # 2. Run Validation, mocking ffprobe to simulate successful embed
    from unittest import mock

    mock_ffprobe_data = {
        "streams": [
            {"codec_type": "video", "codec_name": "h264"},
            {"codec_type": "video", "codec_name": "mjpeg", "disposition": {"attached_pic": 1}},
        ],
        "format": {"tags": {}},
    }

    with mock.patch("vidsmith.downloader.validators.context.subprocess.run") as mock_run:
        mock_run.return_value.stdout = json.dumps(mock_ffprobe_data)
        mock_run.return_value.returncode = 0
        validation = validate_download(job, result)

    assert validation.success is True
    assert validation.thumbnail.embedded is True  # type: ignore

    # 3. Run Cleanup
    cleanup_job_artifacts(job, result.files, validation)

    # 4. Assert Primary Output Remains
    assert media_file.exists()
    assert media_file.read_text() == "dummy media"

    # 5. Assert Temp Artifacts Removed
    assert not temp_thumb.exists()


def test_e2e_cleanup_preserves_saved_thumbnail(temp_output: Path) -> None:
    """A thumbnail the user asked to SAVE is a deliverable, not scaffolding.

    Cleanup only runs after validation has already confirmed success (the
    executor raises before reaching cleanup otherwise), so cleanup no longer
    re-guesses whether an embed worked. Preservation is driven purely by
    intent: SAVE/BOTH thumbnails, and subtitle/thumbnail deliverable jobs, are
    kept; everything else beside a video is swept.
    """
    # 1. Create a mock media file and the saved-thumbnail sidecar
    media_file = temp_output / "video.mp4"
    saved_thumb = temp_output / "video.webp"

    media_file.write_text("dummy media")
    saved_thumb.write_text("dummy thumb")

    job = DownloadJob(
        url="https://youtube.com/watch?v=123",
        media_type=DownloadMediaType.VIDEO,
        output_dir=temp_output,
        thumbnail_mode=ThumbnailMode.SAVE,
        metadata_mode=MetadataMode.NONE,
        subtitle_mode=SubtitleMode.NONE,
    )

    result = DownloadResult(
        job_id="test",
        url="https://youtube.com/watch?v=123",
        status=DownloadResultStatus.COMPLETED,
        output_dir=temp_output,
        files=[media_file, saved_thumb],
    )

    # 2. Run Cleanup
    cleanup_job_artifacts(job, result.files)

    # 3. Assert Primary Output AND the requested sidecar both remain
    assert media_file.exists()
    assert saved_thumb.exists()


def test_e2e_cleanup_sweeps_subtitle_sidecars_for_video(temp_output: Path) -> None:
    """Subtitle sidecars beside a video are always transient — always swept.

    This is the regression that mattered in the field: BOTH-mode captions
    (`video.en.vtt`, `video.hi.vtt`, …) used to survive because deletion hung
    on ffprobe reporting a language tag on the muxed stream. It no longer does.
    """
    media_file = temp_output / "video.mp4"
    media_file.write_text("dummy media")

    subs = [
        temp_output / "video.en.vtt",
        temp_output / "video.hi.vtt",
        temp_output / "video.ta.vtt",
        temp_output / "video.te.srv3",
        temp_output / "video.te.json3",
    ]
    for s in subs:
        s.write_text("dummy sub")

    job = DownloadJob(
        url="https://youtube.com/watch?v=123",
        media_type=DownloadMediaType.VIDEO,
        output_dir=temp_output,
        thumbnail_mode=ThumbnailMode.NONE,
        metadata_mode=MetadataMode.NONE,
        subtitle_mode=SubtitleMode.BOTH,
    )

    result = DownloadResult(
        job_id="test",
        url="https://youtube.com/watch?v=123",
        status=DownloadResultStatus.COMPLETED,
        output_dir=temp_output,
        files=[media_file],
    )

    cleanup_job_artifacts(job, result.files)

    assert media_file.exists()
    for s in subs:
        assert not s.exists()


def test_e2e_cleanup_keeps_subtitle_deliverables(temp_output: Path) -> None:
    """A subtitle-only job's caption files ARE the product — never deleted."""
    en = temp_output / "video.en.vtt"
    hi = temp_output / "video.hi.vtt"
    en.write_text("dummy")
    hi.write_text("dummy")

    job = DownloadJob(
        url="https://youtube.com/watch?v=123",
        media_type=DownloadMediaType.SUBTITLE,
        output_dir=temp_output,
        subtitle_mode=SubtitleMode.BOTH,
    )

    result = DownloadResult(
        job_id="test",
        url="https://youtube.com/watch?v=123",
        status=DownloadResultStatus.COMPLETED,
        output_dir=temp_output,
        files=[en, hi],
    )

    cleanup_job_artifacts(job, result.files)

    assert en.exists()
    assert hi.exists()
