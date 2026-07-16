import json
from pathlib import Path

import pytest

from mediaforge.downloader.cleanup import cleanup_job_artifacts
from mediaforge.downloader.job import (
    DownloadJob,
    DownloadMediaType,
    JobStatus,
    MetadataMode,
    SubtitleMode,
    ThumbnailMode,
)
from mediaforge.downloader.validator import validate_download
from mediaforge.providers.results import DownloadResult

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
        subtitle_mode=SubtitleMode.NONE
    )

    result = DownloadResult(
        job_id="test",
        url="https://youtube.com/watch?v=123",
        status=JobStatus.COMPLETED,
        output_dir=temp_output,
        files=[media_file, temp_thumb]
    )

    # 2. Run Validation, mocking ffprobe to simulate successful embed
    from unittest import mock
    mock_ffprobe_data = {
        "streams": [
            {"codec_type": "video", "codec_name": "h264"},
            {"codec_type": "video", "codec_name": "mjpeg", "disposition": {"attached_pic": 1}}
        ],
        "format": {"tags": {}}
    }

    with mock.patch("mediaforge.downloader.validators.context.subprocess.run") as mock_run:
        mock_run.return_value.stdout = json.dumps(mock_ffprobe_data)
        mock_run.return_value.returncode = 0
        validation = validate_download(job, result)

    assert validation.success is True
    assert validation.thumbnail.embedded is True

    # 3. Run Cleanup
    cleanup_job_artifacts(job, result.files, validation)

    # 4. Assert Primary Output Remains
    assert media_file.exists()
    assert media_file.read_text() == "dummy media"

    # 5. Assert Temp Artifacts Removed
    assert not temp_thumb.exists()

def test_e2e_cleanup_retains_temp_on_failed_embed(temp_output: Path) -> None:
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
        subtitle_mode=SubtitleMode.NONE
    )

    result = DownloadResult(
        job_id="test",
        url="https://youtube.com/watch?v=123",
        status=JobStatus.COMPLETED,
        output_dir=temp_output,
        files=[media_file, temp_thumb]
    )

    # 2. Run Validation, mocking ffprobe to simulate FAILED embed
    from unittest import mock
    mock_ffprobe_data = {
        "streams": [
            {"codec_type": "video", "codec_name": "h264"}
            # NO attached_pic
        ],
        "format": {"tags": {}}
    }

    with mock.patch("mediaforge.downloader.validators.context.subprocess.run") as mock_run:
        mock_run.return_value.stdout = json.dumps(mock_ffprobe_data)
        mock_run.return_value.returncode = 0
        validation = validate_download(job, result)

    assert validation.success is False
    assert validation.thumbnail.embedded is False

    # 3. Run Cleanup
    cleanup_job_artifacts(job, result.files, validation)

    # 4. Assert Primary Output Remains
    assert media_file.exists()

    # 5. Assert Temp Artifacts ARE PRESERVED because embed failed
    assert temp_thumb.exists()
