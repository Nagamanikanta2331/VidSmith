from pathlib import Path

import pytest

from vidsmith.downloader.cleanup import cleanup_job_artifacts
from vidsmith.downloader.job import (
    DownloadJob,
    DownloadMediaType,
    ThumbnailMode,
)
from vidsmith.downloader.validators.models import (
    DownloadValidationResult,
    ThumbnailValidationResult,
)


@pytest.fixture
def dummy_job():
    return DownloadJob(
        url="https://youtube.com/watch?v=dummy",
        media_type=DownloadMediaType.VIDEO,
        output_dir=Path("/tmp/dummy"),
        quality="720",
    )


def create_files(tmp_path: Path, base_name: str, extensions: list[str]) -> list[Path]:
    files = []
    for ext in extensions:
        p = tmp_path / f"{base_name}{ext}"
        p.touch()
        files.append(p)
    return files


def test_cleanup_mp4_embed(tmp_path, dummy_job):
    dummy_job.thumbnail_mode = ThumbnailMode.EMBED
    dummy_job.video_format = "mp4"
    create_files(tmp_path, "video", [".mp4", ".jpg", ".part"])
    final_file = tmp_path / "video.mp4"

    val = DownloadValidationResult()
    val.thumbnail = ThumbnailValidationResult(embedded=True)

    deleted = cleanup_job_artifacts(dummy_job, [final_file], val)
    deleted_names = {p.name for p in deleted}

    assert "video.jpg" in deleted_names
    assert "video.part" in deleted_names
    assert (tmp_path / "video.mp4").exists()
    assert not (tmp_path / "video.jpg").exists()


def test_cleanup_mp4_save(tmp_path, dummy_job):
    dummy_job.thumbnail_mode = ThumbnailMode.SAVE
    dummy_job.video_format = "mp4"
    create_files(tmp_path, "video", [".mp4", ".webp"])
    final_file = tmp_path / "video.mp4"

    val = DownloadValidationResult()
    val.thumbnail = ThumbnailValidationResult(saved=True)

    deleted = cleanup_job_artifacts(dummy_job, [final_file], val)
    deleted_names = {p.name for p in deleted}

    assert "video.webp" not in deleted_names
    assert (tmp_path / "video.mp4").exists()
    assert (tmp_path / "video.webp").exists()


def test_cleanup_mp4_both(tmp_path, dummy_job):
    dummy_job.thumbnail_mode = ThumbnailMode.BOTH
    dummy_job.video_format = "mp4"
    create_files(tmp_path, "video", [".mp4", ".jpg"])
    final_file = tmp_path / "video.mp4"

    val = DownloadValidationResult()
    val.thumbnail = ThumbnailValidationResult(embedded=True, saved=True)

    deleted = cleanup_job_artifacts(dummy_job, [final_file], val)
    deleted_names = {p.name for p in deleted}

    assert "video.jpg" not in deleted_names
    assert (tmp_path / "video.mp4").exists()
    assert (tmp_path / "video.jpg").exists()


def test_cleanup_mkv_embed(tmp_path, dummy_job):
    dummy_job.thumbnail_mode = ThumbnailMode.EMBED
    dummy_job.video_format = "mkv"
    create_files(tmp_path, "video", [".mkv", ".jpg"])
    final_file = tmp_path / "video.mkv"

    val = DownloadValidationResult()
    val.thumbnail = ThumbnailValidationResult(embedded=True)

    deleted = cleanup_job_artifacts(dummy_job, [final_file], val)
    deleted_names = {p.name for p in deleted}

    assert "video.jpg" in deleted_names
    assert (tmp_path / "video.mkv").exists()
    assert not (tmp_path / "video.jpg").exists()


def test_cleanup_audio_embed(tmp_path, dummy_job):
    dummy_job.media_type = DownloadMediaType.AUDIO
    dummy_job.thumbnail_mode = ThumbnailMode.EMBED
    dummy_job.audio_format = "mp3"
    create_files(tmp_path, "audio", [".mp3", ".jpg"])
    final_file = tmp_path / "audio.mp3"

    val = DownloadValidationResult()
    val.thumbnail = ThumbnailValidationResult(embedded=True)

    deleted = cleanup_job_artifacts(dummy_job, [final_file], val)
    deleted_names = {p.name for p in deleted}

    assert "video.jpg" not in deleted_names  # Wait, it's called audio.jpg
    assert "audio.jpg" in deleted_names
    assert (tmp_path / "audio.mp3").exists()
    assert not (tmp_path / "audio.jpg").exists()


def test_cleanup_thumbnail_save(tmp_path, dummy_job):
    dummy_job.media_type = DownloadMediaType.THUMBNAIL
    dummy_job.thumbnail_mode = ThumbnailMode.SAVE
    create_files(tmp_path, "image", [".webp"])
    final_file = tmp_path / "image.webp"

    val = DownloadValidationResult()
    val.thumbnail = ThumbnailValidationResult(saved=True)

    deleted = cleanup_job_artifacts(dummy_job, [final_file], val)
    deleted_names = {p.name for p in deleted}

    assert "image.webp" not in deleted_names
    assert (tmp_path / "image.webp").exists()
