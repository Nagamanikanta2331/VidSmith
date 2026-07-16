import tempfile
from pathlib import Path

from mediaforge.cli.executor import _best_video_job
from mediaforge.cli.wizard.base import WizardState
from mediaforge.cli.wizard.wizards.video import (
    _dynamic_audio_choices,
    _dynamic_format_choices,
    _dynamic_quality_choices,
    _dynamic_subtitle_choices,
    _skip_audio_lang_step,
)
from mediaforge.downloader.cleanup import cleanup_job_artifacts
from mediaforge.downloader.job import (
    DownloadJob,
    DownloadMediaType,
    MetadataMode,
    SubtitleMode,
    ThumbnailMode,
)
from mediaforge.models.media import AnalysisResult, MediaType
from mediaforge.transcript.engine import TranscriptEngine
from mediaforge.transcript.models import (
    TranscriptDocument,
    TranscriptOutputFormat,
    TranscriptSegment,
)


def test_dynamic_resolutions() -> None:
    # Test that video resolutions are dynamically populated from AnalysisResult
    result = AnalysisResult(
        url="https://youtube.com/watch?v=123",
        media_type=MediaType.VIDEO,
        resolutions=["4320p", "2160p", "1080p"],
    )
    state = WizardState({"__media__": result})
    choices = _dynamic_quality_choices(state)

    assert len(choices) == 4  # Best Available + 3 analyzed resolutions
    assert choices[0].value == "best"
    assert choices[1].value == "4320p"
    assert choices[2].value == "2160p"
    assert choices[3].value == "1080p"


def test_video_format_default_is_mp4() -> None:
    state = WizardState({"__media__": AnalysisResult(url="", media_type=MediaType.VIDEO)})
    choices = _dynamic_format_choices(state)

    assert choices[0].value == "mp4"


def test_dynamic_subtitle_languages() -> None:
    # Test that subtitle languages are extracted dynamically, unsupported are dropped,
    # and they are mapped to names.
    result = AnalysisResult(
        url="https://youtube.com/watch?v=123",
        media_type=MediaType.VIDEO,
        subtitle_languages=["en", "hi"],
        automatic_subtitle_languages=["te", "es"],
    )
    state = WizardState({"__media__": result})
    choices = _dynamic_subtitle_choices(state)

    assert len(choices) == 3
    # Priority order is te → hi → ta → en (then other Indian languages).
    assert choices[0].label == "Telugu (Auto)"
    assert choices[0].description == "Auto-generated"
    assert choices[1].label == "Hindi"
    assert choices[1].description == "Manual"
    assert choices[2].label == "English"
    assert choices[2].description == "Manual"


def test_dynamic_audio_languages() -> None:
    # Test dynamic audio languages choice step population and skipping
    result_single = AnalysisResult(
        url="https://youtube.com/watch?v=123",
        media_type=MediaType.VIDEO,
        audio_languages=["en"],
    )
    state_single = WizardState({"__media__": result_single})
    assert _skip_audio_lang_step(state_single) is True

    result_multi = AnalysisResult(
        url="https://youtube.com/watch?v=123",
        media_type=MediaType.VIDEO,
        audio_languages=["en", "es"],
    )
    state_multi = WizardState({"__media__": result_multi})
    assert _skip_audio_lang_step(state_multi) is False

    choices = _dynamic_audio_choices(state_multi)
    assert len(choices) == 2
    assert choices[0].value == "en"
    assert choices[1].value == "es"
    assert choices[1].label == "Spanish"


def test_best_download_defaults() -> None:
    result = AnalysisResult(
        url="https://youtube.com/watch?v=123",
        media_type=MediaType.VIDEO,
        subtitle_languages=["en", "hi"],
        automatic_subtitle_languages=["es"],
    )
    job = _best_video_job(result, Path("/tmp"))
    assert job.video_format == "mp4"
    assert job.format_selector == ""
    assert job.subtitle_mode == SubtitleMode.BOTH
    # Priority order te → hi → ta → en: hi/en resolve to their manual tracks.
    assert job.subtitle_languages == ["hi", "en"]
    # Only the four supported languages are ever requested — each track costs
    # a throttled request before media starts, so the list must stay small.
    assert job.subtitle_requested_languages == ["te", "hi", "ta", "en"]
    assert job.thumbnail_mode == ThumbnailMode.EMBED
    assert job.metadata_mode == MetadataMode.EMBED


def test_cleanup_manager() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        dir_path = Path(temp_dir)
        media_file = dir_path / "video.mp4"
        media_file.touch()

        # Create temporary files
        part_file = dir_path / "video.mp4.part"
        part_file.touch()
        temp_file = dir_path / "video.temp"
        temp_file.touch()
        thumb_file = dir_path / "video.webp"
        thumb_file.touch()
        sub_file = dir_path / "video.en.vtt"
        sub_file.touch()
        json_file = dir_path / "video.info.json"
        json_file.touch()

        job = DownloadJob(
            url="https://youtube.com/watch?v=123",
            media_type=DownloadMediaType.VIDEO,
            output_dir=dir_path,
            subtitle_mode=SubtitleMode.MANUAL,
            thumbnail_mode=ThumbnailMode.EMBED,
            metadata_mode=MetadataMode.EMBED,
        )

        from mediaforge.downloader.validator import DownloadValidationResult
        from mediaforge.downloader.validators.models import (
            SubtitleValidationResult,
            ThumbnailValidationResult,
        )

        validation = DownloadValidationResult(
            subtitle=SubtitleValidationResult(embedded_languages=["en"]),
            thumbnail=ThumbnailValidationResult(embedded=True),
        )
        cleanup_job_artifacts(job, [media_file], validation=validation)

        # Assert cleanup
        assert media_file.exists()
        assert not part_file.exists()
        assert not temp_file.exists()
        assert not thumb_file.exists()
        assert not sub_file.exists()
        assert not json_file.exists()


def test_transcript_outputs() -> None:
    # Test transcript output in VTT and SRT formats
    engine = TranscriptEngine()
    doc = TranscriptDocument(
        segments=[
            TranscriptSegment(start=1.5, end=4.2, text="Hello world"),
            TranscriptSegment(start=5.0, end=7.8, text="Nice to meet you"),
        ],
        title="Test Title",
        language="en",
    )

    srt_out = engine.export(doc, TranscriptOutputFormat.SRT)
    assert "1" in srt_out
    assert "00:00:01,500 --> 00:00:04,200" in srt_out
    assert "Hello world" in srt_out

    vtt_out = engine.export(doc, TranscriptOutputFormat.VTT)
    assert "WEBVTT" in vtt_out
    assert "00:00:01.500 --> 00:00:04.200" in vtt_out
