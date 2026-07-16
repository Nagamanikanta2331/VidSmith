"""FFmpeg-backed media post-processing."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from vidsmith.processing.exceptions import (
    FFmpegNotFoundError,
    FFmpegProcessingError,
    ProcessingValidationError,
)
from vidsmith.processing.models import (
    Chapter,
    ProcessingJob,
    ProcessingOperation,
    ProcessingResult,
    ProcessingStatus,
    SubtitleDisposition,
)
from vidsmith.processing.processor import MediaProcessor


class FFmpegProcessor(MediaProcessor):
    """MediaProcessor implementation that invokes the ffmpeg executable."""

    _SUPPORTED = {
        ProcessingOperation.EMBED_THUMBNAIL,
        ProcessingOperation.EMBED_SUBTITLES,
        ProcessingOperation.EMBED_METADATA,
        ProcessingOperation.MERGE_STREAMS,
        ProcessingOperation.CONVERT_CONTAINER,
        ProcessingOperation.EXTRACT_AUDIO,
    }

    def __init__(self, ffmpeg_path: str = "ffmpeg") -> None:
        self.ffmpeg_path = ffmpeg_path

    def supports(self, operation: ProcessingOperation) -> bool:
        return operation in self._SUPPORTED

    def process(self, job: ProcessingJob) -> ProcessingResult:
        self._validate_job(job)
        self._ensure_ffmpeg()
        job.output_path.parent.mkdir(parents=True, exist_ok=True)

        with TemporaryDirectory(prefix="vidsmith-ffmpeg-") as temp_dir:
            current_input = job.input_path
            for index, operation in enumerate(job.operations):
                is_last = index == len(job.operations) - 1
                output_path = (
                    job.output_path if is_last else self._temp_output(job, temp_dir, index)
                )
                command = self._command_for(
                    operation, job, current_input, output_path, Path(temp_dir)
                )
                self._run(command, operation)
                current_input = output_path

        return ProcessingResult(
            job_id=job.job_id,
            status=ProcessingStatus.COMPLETED,
            output_path=job.output_path,
            operations=list(job.operations),
            files=[job.output_path],
            message="Processing complete.",
        )

    def _command_for(
        self,
        operation: ProcessingOperation,
        job: ProcessingJob,
        input_path: Path | None,
        output_path: Path,
        temp_dir: Path,
    ) -> list[str]:
        builders = {
            ProcessingOperation.EMBED_THUMBNAIL: self._embed_thumbnail_command,
            ProcessingOperation.EMBED_SUBTITLES: self._embed_subtitles_command,
            ProcessingOperation.EMBED_METADATA: self._embed_metadata_command,
            ProcessingOperation.MERGE_STREAMS: self._merge_streams_command,
            ProcessingOperation.CONVERT_CONTAINER: self._convert_container_command,
            ProcessingOperation.EXTRACT_AUDIO: self._extract_audio_command,
        }
        return builders[operation](job, input_path, output_path, temp_dir)

    def _embed_thumbnail_command(
        self,
        job: ProcessingJob,
        input_path: Path | None,
        output_path: Path,
        temp_dir: Path,
    ) -> list[str]:
        input_path = self._require_input(input_path, ProcessingOperation.EMBED_THUMBNAIL)
        if job.thumbnail_path is None:
            raise ProcessingValidationError("thumbnail_path is required to embed a thumbnail.")

        command = self._base_command(job)
        command.extend(["-i", str(input_path), "-i", str(job.thumbnail_path)])
        command.extend(["-map", "0", "-map", "1", "-c", "copy"])
        if output_path.suffix.lower() in {".mp3", ".m4a", ".mp4"}:
            command.extend(["-disposition:v:1", "attached_pic"])
        command.append(str(output_path))
        return command

    def _embed_subtitles_command(
        self,
        job: ProcessingJob,
        input_path: Path | None,
        output_path: Path,
        temp_dir: Path,
    ) -> list[str]:
        input_path = self._require_input(input_path, ProcessingOperation.EMBED_SUBTITLES)
        if not job.subtitles:
            raise ProcessingValidationError("At least one subtitle input is required.")

        command = self._base_command(job)
        command.extend(["-i", str(input_path)])
        for subtitle in job.subtitles:
            command.extend(["-i", str(subtitle.path)])

        command.extend(["-map", "0"])
        for subtitle_index in range(len(job.subtitles)):
            command.extend(["-map", f"{subtitle_index + 1}:0"])

        command.extend(["-c", "copy"])
        subtitle_codec = "mov_text" if output_path.suffix.lower() == ".mp4" else "copy"
        command.extend(["-c:s", subtitle_codec])

        for stream_index, subtitle in enumerate(job.subtitles):
            command.extend([f"-metadata:s:s:{stream_index}", f"language={subtitle.language}"])
            if subtitle.title:
                command.extend([f"-metadata:s:s:{stream_index}", f"title={subtitle.title}"])
            if subtitle.disposition != SubtitleDisposition.OPTIONAL:
                command.extend([f"-disposition:s:{stream_index}", subtitle.disposition.value])

        command.append(str(output_path))
        return command

    def _embed_metadata_command(
        self,
        job: ProcessingJob,
        input_path: Path | None,
        output_path: Path,
        temp_dir: Path,
    ) -> list[str]:
        input_path = self._require_input(input_path, ProcessingOperation.EMBED_METADATA)
        if job.metadata is None:
            raise ProcessingValidationError("metadata is required to embed metadata.")

        metadata_file = self._chapter_metadata_file(job.metadata.chapters, output_path, temp_dir)
        command = self._base_command(job)
        command.extend(["-i", str(input_path)])
        if metadata_file is not None:
            command.extend(["-i", str(metadata_file), "-map_metadata", "1"])
        command.extend(["-map", "0", "-c", "copy"])
        self._append_metadata_args(command, job)
        command.append(str(output_path))
        return command

    def _merge_streams_command(
        self,
        job: ProcessingJob,
        input_path: Path | None,
        output_path: Path,
        temp_dir: Path,
    ) -> list[str]:
        video_path = job.video_path or input_path
        if video_path is None or job.audio_path is None:
            raise ProcessingValidationError(
                "video_path and audio_path are required to merge streams."
            )

        command = self._base_command(job)
        command.extend(["-i", str(video_path), "-i", str(job.audio_path)])
        command.extend(["-map", "0:v:0", "-map", "1:a:0", "-c", "copy", "-shortest"])
        command.append(str(output_path))
        return command

    def _convert_container_command(
        self,
        job: ProcessingJob,
        input_path: Path | None,
        output_path: Path,
        temp_dir: Path,
    ) -> list[str]:
        input_path = self._require_input(input_path, ProcessingOperation.CONVERT_CONTAINER)
        container = self._target_container(job, output_path)
        command = self._base_command(job)
        command.extend(["-i", str(input_path), "-map", "0", "-c", "copy"])
        if container == "mp4":
            command.extend(["-movflags", "+faststart"])
        command.append(str(output_path))
        return command

    def _extract_audio_command(
        self,
        job: ProcessingJob,
        input_path: Path | None,
        output_path: Path,
        temp_dir: Path,
    ) -> list[str]:
        input_path = self._require_input(input_path, ProcessingOperation.EXTRACT_AUDIO)
        audio_format = (job.audio_format or output_path.suffix.lstrip(".")).lower()
        codec = self._audio_codec(audio_format)

        command = self._base_command(job)
        command.extend(["-i", str(input_path), "-vn", "-map", "0:a:0"])
        if codec == "copy":
            command.extend(["-c:a", "copy"])
        else:
            command.extend(["-c:a", codec])
        command.append(str(output_path))
        return command

    def _base_command(self, job: ProcessingJob) -> list[str]:
        return [self.ffmpeg_path, "-y" if job.overwrite else "-n"]

    def _run(self, command: list[str], operation: ProcessingOperation) -> None:
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                check=False,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except FileNotFoundError:
            raise FFmpegNotFoundError("ffmpeg executable was not found.") from None
        except OSError:
            raise FFmpegProcessingError(operation.value) from None

        if result.returncode != 0:
            raise FFmpegProcessingError(operation.value, result.returncode)

    def _validate_job(self, job: ProcessingJob) -> None:
        if not job.operations:
            raise ProcessingValidationError("At least one processing operation is required.")
        for operation in job.operations:
            if not self.supports(operation):
                raise ProcessingValidationError(
                    f"Unsupported processing operation: {operation.value}"
                )

    def _ensure_ffmpeg(self) -> None:
        if shutil.which(self.ffmpeg_path) is None and not Path(self.ffmpeg_path).exists():
            raise FFmpegNotFoundError("ffmpeg executable was not found.")

    def _require_input(self, input_path: Path | None, operation: ProcessingOperation) -> Path:
        if input_path is None:
            raise ProcessingValidationError(f"input_path is required for {operation.value}.")
        return input_path

    def _target_container(self, job: ProcessingJob, output_path: Path) -> str:
        container = (job.target_container or output_path.suffix.lstrip(".")).lower()
        if container not in {"mp4", "mkv", "webm"}:
            raise ProcessingValidationError(f"Unsupported target container: {container}")
        return container

    def _audio_codec(self, audio_format: str) -> str:
        codecs = {
            "aac": "aac",
            "flac": "flac",
            "m4a": "aac",
            "mp3": "libmp3lame",
            "opus": "libopus",
            "wav": "pcm_s16le",
            "webm": "copy",
        }
        return codecs.get(audio_format, "copy")

    def _append_metadata_args(self, command: list[str], job: ProcessingJob) -> None:
        metadata = job.metadata
        if metadata is None:
            return
        fields = {
            "title": metadata.title,
            "artist": metadata.uploader,
            "comment": metadata.description,
            "date": metadata.upload_date,
        }
        for key, value in fields.items():
            if value:
                command.extend(["-metadata", f"{key}={value}"])

    def _chapter_metadata_file(
        self,
        chapters: list[Chapter],
        output_path: Path,
        temp_dir: Path,
    ) -> Path | None:
        if not chapters:
            return None
        metadata_path = temp_dir / f"{output_path.stem}.chapters.ffmetadata"
        lines = [";FFMETADATA1"]
        for chapter in chapters:
            lines.extend(
                [
                    "[CHAPTER]",
                    "TIMEBASE=1/1000",
                    f"START={chapter.start_ms}",
                    f"END={chapter.end_ms}",
                    f"title={chapter.title}",
                ]
            )
        metadata_path.write_text("\n".join(lines), encoding="utf-8")
        return metadata_path

    def _temp_output(self, job: ProcessingJob, temp_dir: str, index: int) -> Path:
        suffix = job.output_path.suffix or ".tmp"
        return Path(temp_dir) / f"{job.job_id}-{index}{suffix}"
