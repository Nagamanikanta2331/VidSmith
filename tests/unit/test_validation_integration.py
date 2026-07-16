import json
from pathlib import Path
from unittest import mock

import pytest

from vidsmith.downloader.job import (  # type: ignore
    DownloadJob,
    DownloadMediaType,
    MetadataMode,
    ThumbnailMode,
)
from vidsmith.downloader.validator import validate_download
from vidsmith.downloader.validators import ValidationErrorCode
from vidsmith.providers.results import DownloadResult, DownloadResultStatus


@pytest.fixture
def temp_output(tmp_path: Path) -> Path:
    return tmp_path


def _create_mock_job(media_type: DownloadMediaType, temp_dir: Path, **kwargs) -> DownloadJob:
    return DownloadJob(
        url="https://youtube.com/watch?v=123", media_type=media_type, output_dir=temp_dir, **kwargs
    )


def _create_mock_result(temp_dir: Path, files: list[Path]) -> DownloadResult:
    return DownloadResult(
        job_id="test",
        url="https://youtube.com/watch?v=123",
        status=DownloadResultStatus.COMPLETED,
        output_dir=temp_dir,
        files=files,
    )


def test_integration_mp4_h264_with_thumbnail_and_metadata(temp_output: Path) -> None:
    media_file = temp_output / "video.mp4"
    media_file.write_text("dummy")

    job = _create_mock_job(
        DownloadMediaType.VIDEO,
        temp_output,
        thumbnail_mode=ThumbnailMode.EMBED,
        metadata_mode=MetadataMode.EMBED,
    )
    result = _create_mock_result(temp_output, [media_file])

    mock_ffprobe_data = {
        "format": {"tags": {"title": "Test Video"}},
        "chapters": [{"id": 1}],
        "streams": [
            {"codec_type": "video", "codec_name": "h264"},
            {"codec_type": "audio", "codec_name": "aac"},
            {"codec_type": "video", "codec_name": "mjpeg", "disposition": {"attached_pic": 1}},
        ],
    }

    with mock.patch("vidsmith.downloader.validators.context.subprocess.run") as mock_run:
        mock_run.return_value.stdout = json.dumps(mock_ffprobe_data)
        mock_run.return_value.returncode = 0

        validation = validate_download(job, result)

        assert mock_run.call_count == 1

    assert validation.success is True
    assert validation.thumbnail.embedded is True  # type: ignore
    assert validation.metadata.embedded is True  # type: ignore
    assert validation.metadata.chapter_count == 1  # type: ignore


def test_integration_zero_byte_file(temp_output: Path) -> None:
    media_file = temp_output / "video.mp4"
    media_file.touch()  # Zero bytes

    job = _create_mock_job(DownloadMediaType.VIDEO, temp_output)
    result = _create_mock_result(temp_output, [media_file])

    with mock.patch("vidsmith.downloader.validators.context.subprocess.run") as mock_run:
        validation = validate_download(job, result)
        assert mock_run.call_count == 0  # Should fail file check before ffprobe

    assert validation.success is False
    assert validation.error_code == ValidationErrorCode.FILE_EMPTY


def test_integration_missing_file(temp_output: Path) -> None:
    media_file = temp_output / "video.mp4"

    job = _create_mock_job(DownloadMediaType.VIDEO, temp_output)
    result = _create_mock_result(temp_output, [media_file])

    with mock.patch("vidsmith.downloader.validators.context.subprocess.run") as mock_run:
        validation = validate_download(job, result)
        assert mock_run.call_count == 0

    assert validation.success is False
    assert validation.error_code == ValidationErrorCode.FILE_MISSING


def test_integration_ffprobe_failure(temp_output: Path) -> None:
    media_file = temp_output / "video.mp4"
    media_file.write_text("dummy")

    job = _create_mock_job(
        DownloadMediaType.VIDEO,
        temp_output,
        thumbnail_mode=ThumbnailMode.EMBED,
        metadata_mode=MetadataMode.EMBED,
    )
    result = _create_mock_result(temp_output, [media_file])

    with mock.patch("vidsmith.downloader.validators.context.subprocess.run") as mock_run:
        mock_run.side_effect = Exception("ffprobe crashed")
        validation = validate_download(job, result)
        assert mock_run.call_count == 1

    # Should gracefully fail specific modules without crashing
    assert validation.success is True
    assert validation.thumbnail.embedded is False  # type: ignore
    assert validation.metadata.embedded is True  # type: ignore


def test_integration_mp3_with_artwork(temp_output: Path) -> None:
    media_file = temp_output / "audio.mp3"
    media_file.write_text("dummy")

    job = _create_mock_job(DownloadMediaType.AUDIO, temp_output)
    result = _create_mock_result(temp_output, [media_file])

    # MP3 artwork is checked with mutagen first
    with (
        mock.patch("vidsmith.downloader.validators.context.subprocess.run") as mock_run,
        mock.patch("mutagen.mp3.MP3") as mock_mp3,
    ):
        mock_mp3.return_value.tags = {"APIC:cover": "data"}
        mock_run.return_value.stdout = '{"format": {"tags": {"title": "Test"}}, "streams": []}'
        mock_run.return_value.returncode = 0

        validation = validate_download(job, result)
        assert mock_run.call_count == 1

    assert validation.success is True
    assert validation.audio.artwork_status == "Embedded"  # type: ignore
    assert validation.audio.title_present is True  # type: ignore
