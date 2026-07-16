from pathlib import Path

import pytest

from mediaforge.downloader.cleanup import cleanup_job_artifacts
from mediaforge.downloader.job import DownloadJob, DownloadMediaType
from mediaforge.downloader.validator import DownloadValidationResult


@pytest.fixture
def temp_job_dir(tmp_path: Path):
    d = tmp_path / "downloads"
    d.mkdir()
    return d


def test_cleanup_enabled(temp_job_dir: Path):
    job = DownloadJob(url="http", media_type=DownloadMediaType.VIDEO, output_dir=temp_job_dir)
    final_file = temp_job_dir / "video.mp4"
    final_file.touch()

    part_file = temp_job_dir / "video.mp4.part"
    part_file.touch()

    val = DownloadValidationResult(success=True)

    cleanup_job_artifacts(job, [final_file], val, cleanup_enabled=True, keep_temp_files=False)

    assert final_file.exists()
    assert not part_file.exists()


def test_cleanup_disabled(temp_job_dir: Path):
    job = DownloadJob(url="http", media_type=DownloadMediaType.VIDEO, output_dir=temp_job_dir)
    final_file = temp_job_dir / "video.mp4"
    final_file.touch()

    part_file = temp_job_dir / "video.mp4.part"
    part_file.touch()

    val = DownloadValidationResult(success=True)

    cleanup_job_artifacts(job, [final_file], val, cleanup_enabled=False, keep_temp_files=False)

    assert final_file.exists()
    assert part_file.exists()


def test_keep_temp_files(temp_job_dir: Path):
    job = DownloadJob(url="http", media_type=DownloadMediaType.VIDEO, output_dir=temp_job_dir)
    final_file = temp_job_dir / "video.mp4"
    final_file.touch()

    part_file = temp_job_dir / "video.mp4.part"
    part_file.touch()

    val = DownloadValidationResult(success=True)

    cleanup_job_artifacts(job, [final_file], val, cleanup_enabled=True, keep_temp_files=True)

    assert final_file.exists()
    assert part_file.exists()
