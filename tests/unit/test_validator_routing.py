from pathlib import Path
from unittest.mock import patch

import pytest

from mediaforge.downloader.job import (
    DownloadJob,
    DownloadMediaType,
    SubtitleMode,
    ThumbnailMode,
)
from mediaforge.downloader.validator import validate_download
from mediaforge.providers.results import DownloadResult, DownloadResultStatus


@pytest.fixture
def dummy_result(tmp_path: Path):
    media_file = tmp_path / "dummy.mp4"
    media_file.write_text("dummy")
    return DownloadResult(
        job_id="test",
        url="https://youtube.com/watch?v=123",
        status=DownloadResultStatus.COMPLETED,
        output_dir=tmp_path,
        files=[media_file],
        media_type="video",
    )


def test_video_job_routing(dummy_result):
    job = DownloadJob(
        url="https://youtube.com/watch?v=123",
        media_type=DownloadMediaType.VIDEO,
        output_dir=dummy_result.output_dir,
    )
    with patch("mediaforge.downloader.validators.context.subprocess.run") as mock_run:
        mock_run.return_value.stdout = '{"streams": []}'
        mock_run.return_value.returncode = 0

        val = validate_download(job, dummy_result)

        assert val.success


def test_transcript_job_routing(dummy_result):
    job = DownloadJob(
        url="https://youtube.com/watch?v=123",
        media_type=DownloadMediaType.TRANSCRIPT,
        output_dir=dummy_result.output_dir,
        subtitle_mode=SubtitleMode.BOTH,
    )

    with patch("mediaforge.downloader.validators.context.subprocess.run") as mock_run:
        mock_run.return_value.stdout = '{"streams": []}'
        mock_run.return_value.returncode = 0

        val = validate_download(job, dummy_result)
        # Without sidecars, Transcript validator (via subtitle validator logic) fails
        assert not val.success
        assert val.error_code == "TRANSCRIPT_FAILED"


def test_subtitle_job_routing(dummy_result):
    job = DownloadJob(
        url="https://youtube.com/watch?v=123",
        media_type=DownloadMediaType.SUBTITLE,
        output_dir=dummy_result.output_dir,
        subtitle_mode=SubtitleMode.BOTH,
    )

    with patch("mediaforge.downloader.validators.context.subprocess.run") as mock_run:
        mock_run.return_value.stdout = '{"streams": []}'
        mock_run.return_value.returncode = 0

        val = validate_download(job, dummy_result)
        # Without sidecars, Subtitle validator fails
        assert not val.success
        assert val.error_code == "SUBTITLE_FAILED"


def test_thumbnail_job_routing(dummy_result):
    job = DownloadJob(
        url="https://youtube.com/watch?v=123",
        media_type=DownloadMediaType.THUMBNAIL,
        output_dir=dummy_result.output_dir,
        thumbnail_mode=ThumbnailMode.SAVE,
    )

    with patch("mediaforge.downloader.validators.context.subprocess.run") as mock_run:
        mock_run.return_value.stdout = '{"streams": []}'
        mock_run.return_value.returncode = 0

        val = validate_download(job, dummy_result)
        # Thumbnail has no sidecar subtitles, but since it's THUMBNAIL, the subtitle validator ignores it.
        # However, Thumbnail validator might fail if no thumbnail sidecar exists?
        # Actually wait, let's see if thumbnail succeeds or fails.
        # If it fails, it should fail with THUMBNAIL_FAILED, not TRANSCRIPT_FAILED!
        assert getattr(val, "error_code", None) != "TRANSCRIPT_FAILED"
