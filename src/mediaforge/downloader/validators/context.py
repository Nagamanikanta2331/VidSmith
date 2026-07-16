import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from mediaforge.downloader.job import DownloadJob, DownloadMediaType
from mediaforge.providers.results import DownloadResult


@dataclass(frozen=True)
class ValidationContext:
    job: DownloadJob
    result: DownloadResult
    primary_output: Path | None
    exists: bool
    size_bytes: int
    is_audio: bool
    is_video: bool
    ffprobe_data: dict | None
    mutagen_has_artwork: bool | None


def build_context(
    job: DownloadJob, result: DownloadResult, primary_output: Path | None
) -> ValidationContext:
    exists = False
    size_bytes = 0
    is_audio = job.media_type == DownloadMediaType.AUDIO
    is_video = job.media_type == DownloadMediaType.VIDEO
    ffprobe_data = None
    mutagen_has_artwork = None

    if primary_output and primary_output.exists() and primary_output.is_file():
        exists = True
        size_bytes = primary_output.stat().st_size

        if size_bytes > 0:
            if shutil.which("ffprobe"):
                try:
                    cmd = [
                        "ffprobe",
                        "-v",
                        "error",
                        "-show_streams",
                        "-show_format",
                        "-show_chapters",
                        "-of",
                        "json",
                        str(primary_output),
                    ]
                    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
                    ffprobe_data = json.loads(res.stdout)
                except Exception:
                    pass

            if is_audio:
                mutagen_has_artwork = False
                try:
                    ext = primary_output.suffix.lower()
                    if ext == ".mp3":
                        import mutagen.mp3

                        audio = mutagen.mp3.MP3(str(primary_output))
                        mutagen_has_artwork = any(key.startswith("APIC") for key in audio.tags)  # type: ignore
                    elif ext in {".m4a", ".m4b"}:
                        import mutagen.mp4

                        audio = mutagen.mp4.MP4(str(primary_output))  # type: ignore
                        mutagen_has_artwork = "covr" in audio.tags  # type: ignore
                    elif ext == ".flac":
                        import mutagen.flac

                        audio = mutagen.flac.FLAC(str(primary_output))  # type: ignore
                        mutagen_has_artwork = len(audio.pictures) > 0  # type: ignore
                except Exception:
                    pass

    return ValidationContext(
        job=job,
        result=result,
        primary_output=primary_output,
        exists=exists,
        size_bytes=size_bytes,
        is_audio=is_audio,
        is_video=is_video,
        ffprobe_data=ffprobe_data,
        mutagen_has_artwork=mutagen_has_artwork,
    )
