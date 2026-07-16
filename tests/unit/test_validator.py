import json
import tempfile
from pathlib import Path
from unittest import mock
from unittest.mock import MagicMock, patch

import pytest

from vidsmith.downloader.job import DownloadJob, DownloadMediaType, SubtitleMode  # type: ignore
from vidsmith.downloader.validator import validate_download
from vidsmith.providers.results import DownloadResultStatus
from vidsmith.providers.youtube import DownloadResult


@pytest.fixture
def temp_dir() -> Path:  # type: ignore
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)


def test_validator_sidecar_detection(temp_dir: Path) -> None:
    job = DownloadJob(
        url="https://youtube.com/watch?v=123",
        media_type=DownloadMediaType.VIDEO,
        output_dir=temp_dir,
        subtitle_mode=SubtitleMode.MANUAL,
        subtitle_languages=["en", "hi"],
    )

    media_file = temp_dir / "video.mp4"
    en_sub = temp_dir / "video.en.vtt"
    hi_sub = temp_dir / "video.hi.vtt"

    media_file.write_text("dummy")
    en_sub.write_text("dummy")
    hi_sub.write_text("dummy")

    result = DownloadResult(
        job_id="test",
        url=job.url,
        status=DownloadResultStatus.COMPLETED,
        output_dir=temp_dir,
        files=[media_file, en_sub, hi_sub],
    )

    with mock.patch("vidsmith.downloader.validators.context.subprocess.run") as mock_run:
        mock_run.return_value.stdout = '{"streams": []}'
        mock_run.return_value.returncode = 0
        val = validate_download(job, result)

        assert "en" in val.subtitle.sidecar_languages
        assert "hi" in val.subtitle.sidecar_languages
        assert len(val.subtitle.embedded_languages) == 0
        assert val.subtitle.success is True


def test_validator_embedded_detection(temp_dir: Path) -> None:
    job = DownloadJob(
        url="https://youtube.com/watch?v=123",
        media_type=DownloadMediaType.VIDEO,
        output_dir=temp_dir,
        subtitle_mode=SubtitleMode.BOTH,
        subtitle_languages=["en", "hi"],
    )

    media_file = temp_dir / "video.mp4"
    media_file.write_text("dummy")

    result = DownloadResult(
        job_id="test",
        url=job.url,
        status=DownloadResultStatus.COMPLETED,
        output_dir=temp_dir,
        files=[media_file],
    )

    with mock.patch("vidsmith.downloader.validators.context.subprocess.run") as mock_run:
        mock_run.return_value.stdout = '{"streams": [{"codec_type": "subtitle", "tags": {"language": "en"}}, {"codec_type": "subtitle", "tags": {"language": "hi"}}]}'
        mock_run.return_value.returncode = 0
        val = validate_download(job, result)

        assert "en" in val.subtitle.embedded_languages
        assert "hi" in val.subtitle.embedded_languages
        assert len(val.subtitle.sidecar_languages) == 0
        assert val.subtitle.success is True


def test_validator_missing_subtitle_detection(temp_dir: Path) -> None:
    job = DownloadJob(
        url="https://youtube.com/watch?v=123",
        media_type=DownloadMediaType.VIDEO,
        output_dir=temp_dir,
        subtitle_mode=SubtitleMode.MANUAL,
        subtitle_languages=["en", "hi"],
    )

    media_file = temp_dir / "video.mp4"
    en_sub = temp_dir / "video.en.vtt"

    media_file.write_text("dummy")
    en_sub.write_text("dummy")

    result = DownloadResult(
        job_id="test",
        url=job.url,
        status=DownloadResultStatus.COMPLETED,
        output_dir=temp_dir,
        files=[media_file, en_sub],
    )

    with mock.patch("vidsmith.downloader.validators.context.subprocess.run") as mock_run:
        mock_run.return_value.stdout = '{"streams": []}'
        mock_run.return_value.returncode = 0
        val = validate_download(job, result)

        assert "en" in val.subtitle.sidecar_languages
        assert "hi" in val.subtitle.failed_languages
        assert val.subtitle.success is True


def test_validator_subtitle_only_success(temp_dir: Path) -> None:
    job = DownloadJob(
        url="https://youtube.com/watch?v=123",
        media_type=DownloadMediaType.TRANSCRIPT,
        output_dir=temp_dir,
        subtitle_mode=SubtitleMode.MANUAL,
        subtitle_languages=["en"],
    )

    en_sub = temp_dir / "video.en.vtt"
    en_sub.write_text("dummy")

    result = DownloadResult(
        job_id="test",
        url=job.url,
        status=DownloadResultStatus.COMPLETED,
        output_dir=temp_dir,
        files=[en_sub],
    )

    with mock.patch("vidsmith.downloader.validators.context.subprocess.run") as mock_run:
        mock_run.return_value.stdout = '{"streams": []}'
        mock_run.return_value.returncode = 0
        val = validate_download(job, result)

        assert "en" in val.subtitle.sidecar_languages
        assert val.subtitle.success is True


def test_validator_subtitle_only_failure_when_zero_files(temp_dir: Path) -> None:
    job = DownloadJob(
        url="https://youtube.com/watch?v=123",
        media_type=DownloadMediaType.TRANSCRIPT,
        output_dir=temp_dir,
        subtitle_mode=SubtitleMode.MANUAL,
        subtitle_languages=["en"],
    )

    result = DownloadResult(
        job_id="test",
        url=job.url,
        status=DownloadResultStatus.COMPLETED,
        output_dir=temp_dir,
        files=[],
    )

    with mock.patch("vidsmith.downloader.validators.context.subprocess.run") as mock_run:
        mock_run.return_value.stdout = '{"streams": []}'
        mock_run.return_value.returncode = 0
        val = validate_download(job, result)

        assert val.success is False
        assert val.error_code == "FILE_MISSING"


@patch("vidsmith.downloader.validators.context.subprocess.run")
def test_validate_audio_mp3_artwork(mock_run, tmp_path):
    job = DownloadJob(url="http", media_type=DownloadMediaType.AUDIO, output_dir=tmp_path)
    primary = tmp_path / "song.mp3"
    primary.write_text("dummy")

    mock_run.return_value = MagicMock(
        stdout=json.dumps(
            {
                "streams": [{"codec_type": "video", "disposition": {"attached_pic": 1}}],
                "format": {"tags": {"title": "T", "artist": "A"}},
            }
        )
    )

    result = DownloadResult(
        job_id="test",
        url=job.url,
        status=DownloadResultStatus.COMPLETED,
        output_dir=tmp_path,
        files=[primary],
    )
    val = validate_download(job, result)

    assert val.audio.artwork_status == "Embedded"  # type: ignore
    assert val.audio.metadata_present is True  # type: ignore
    assert val.audio.title_present is True  # type: ignore


@patch("vidsmith.downloader.validators.context.subprocess.run")
def test_validate_audio_mp3_artwork_missing(mock_run, tmp_path):
    job = DownloadJob(url="http", media_type=DownloadMediaType.AUDIO, output_dir=tmp_path)
    primary = tmp_path / "song.mp3"
    primary.write_text("dummy")

    mock_run.return_value = MagicMock(
        stdout=json.dumps({"streams": [{"codec_type": "audio"}], "format": {"tags": {}}})
    )

    result = DownloadResult(
        job_id="test",
        url=job.url,
        status=DownloadResultStatus.COMPLETED,
        output_dir=tmp_path,
        files=[primary],
    )
    val = validate_download(job, result)

    assert val.audio.artwork_status == "Missing"  # type: ignore
    assert val.audio.metadata_present is False  # type: ignore


@patch("vidsmith.downloader.validators.context.subprocess.run")
def test_validate_audio_m4a_artwork(mock_run, tmp_path):
    job = DownloadJob(url="http", media_type=DownloadMediaType.AUDIO, output_dir=tmp_path)
    primary = tmp_path / "song.m4a"
    primary.write_text("dummy")

    mock_run.return_value = MagicMock(
        stdout=json.dumps(
            {
                "streams": [{"codec_type": "video", "disposition": {"attached_pic": 1}}],
                "format": {"tags": {}},
            }
        )
    )

    result = DownloadResult(
        job_id="test",
        url=job.url,
        status=DownloadResultStatus.COMPLETED,
        output_dir=tmp_path,
        files=[primary],
    )
    val = validate_download(job, result)

    assert val.audio.artwork_status == "Embedded"  # type: ignore


@patch("vidsmith.downloader.validators.context.subprocess.run")
def test_validate_audio_unsupported_artwork(mock_run, tmp_path):
    job = DownloadJob(url="http", media_type=DownloadMediaType.AUDIO, output_dir=tmp_path)
    primary = tmp_path / "song.aac"
    primary.write_text("dummy")

    mock_run.return_value = MagicMock(stdout=json.dumps({"streams": [], "format": {}}))

    result = DownloadResult(
        job_id="test",
        url=job.url,
        status=DownloadResultStatus.COMPLETED,
        output_dir=tmp_path,
        files=[primary],
    )
    val = validate_download(job, result)

    assert val.audio.artwork_status == "Unsupported"  # type: ignore


@patch("vidsmith.downloader.validators.context.subprocess.run")
def test_validate_audio_metadata_complete(mock_run, tmp_path):
    job = DownloadJob(url="http", media_type=DownloadMediaType.AUDIO, output_dir=tmp_path)
    primary = tmp_path / "song.mp3"
    primary.write_text("dummy")

    mock_run.return_value = MagicMock(
        stdout=json.dumps(
            {
                "streams": [],
                "format": {
                    "tags": {"title": "Title", "artist": "Artist", "album": "Album", "date": "2024"}
                },
            }
        )
    )

    result = DownloadResult(
        job_id="test",
        url=job.url,
        status=DownloadResultStatus.COMPLETED,
        output_dir=tmp_path,
        files=[primary],
    )
    val = validate_download(job, result)

    assert val.audio.metadata_present is True  # type: ignore
    assert val.audio.title_present is True  # type: ignore
    assert val.audio.artist_present is True  # type: ignore
    assert val.audio.album_present is True  # type: ignore
    assert val.audio.date_present is True  # type: ignore


@patch("vidsmith.downloader.validators.context.subprocess.run")
def test_validate_audio_metadata_partially_missing(mock_run, tmp_path):
    job = DownloadJob(url="http", media_type=DownloadMediaType.AUDIO, output_dir=tmp_path)
    primary = tmp_path / "song.mp3"
    primary.write_text("dummy")

    mock_run.return_value = MagicMock(
        stdout=json.dumps({"streams": [], "format": {"tags": {"title": "Title"}}})
    )

    result = DownloadResult(
        job_id="test",
        url=job.url,
        status=DownloadResultStatus.COMPLETED,
        output_dir=tmp_path,
        files=[primary],
    )
    val = validate_download(job, result)

    assert val.audio.metadata_present is True  # type: ignore
    assert val.audio.title_present is True  # type: ignore
    assert val.audio.artist_present is False  # type: ignore
    assert val.audio.album_present is False  # type: ignore


@patch("vidsmith.downloader.validators.context.subprocess.run")
def test_validate_audio_validation_failures(mock_run, tmp_path):
    job = DownloadJob(url="http", media_type=DownloadMediaType.AUDIO, output_dir=tmp_path)
    primary = tmp_path / "song.mp3"
    primary.write_text("dummy")

    # Simulate ffprobe crashing/erroring
    mock_run.side_effect = Exception("ffprobe error")

    result = DownloadResult(
        job_id="test",
        url=job.url,
        status=DownloadResultStatus.COMPLETED,
        output_dir=tmp_path,
        files=[primary],
    )
    val = validate_download(job, result)

    # Should not crash, status should be what was initialized
    assert (
        val.audio.artwork_status == "Missing"
    )  # since mp3 is supported but check failed  # type: ignore
    assert val.audio.metadata_present is False  # type: ignore
