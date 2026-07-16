from unittest import mock

import pytest

from mediaforge.cli.executor import execute_transcript
from mediaforge.downloader.validator import DownloadValidationResult
from mediaforge.downloader.validators.models import SubtitleValidationResult
from mediaforge.providers.results import DownloadResult, DownloadResultStatus
from mediaforge.transcript.models import TranscriptOutputFormat, TranscriptResult


class DummyState(dict):
    pass


class DummyResult:
    def __init__(self, url="https://youtube.com/watch?v=123", title="Test Title"):
        self.url = url
        self.title = title
        self.subtitle_languages = ["en"]
        self.automatic_subtitle_languages = []


@pytest.fixture
def state():
    return DummyState(
        {
            "output_dir": "tests_output",
            "language": "en",
            "output_format": "txt",
        }
    )


@pytest.fixture
def analysis_result():
    return DummyResult()


@mock.patch("mediaforge.cli.executor.Prompt.ask")
@mock.patch("mediaforge.cli.executor._get_provider")
@mock.patch("mediaforge.cli.executor.validate_download")
@mock.patch("mediaforge.transcript.engine.TranscriptEngine")
@mock.patch("mediaforge.cli.executor._show_success")
@mock.patch("mediaforge.cli.executor._show_error")
def test_execute_transcript_success(
    mock_show_error,
    mock_show_success,
    mock_engine,
    mock_validate,
    mock_get_provider,
    mock_prompt,
    state,
    analysis_result,
    tmp_path,
):
    state["output_dir"] = str(tmp_path)

    # Mock Provider
    mock_provider = mock.Mock()
    mock_get_provider.return_value = mock_provider

    # Mock Subtitle VTT file
    vtt_file = tmp_path / "Test_Title.en.vtt"
    vtt_file.touch()

    dl_result = DownloadResult(
        job_id="job123",
        url=analysis_result.url,
        status=DownloadResultStatus.COMPLETED,
        output_dir=tmp_path,
        media_type="transcript",
        files=[vtt_file],
    )
    mock_provider.download_transcript.return_value = dl_result

    # Mock Validation
    mock_validate.return_value = DownloadValidationResult(
        primary_output=None,
        subtitle=SubtitleValidationResult(sidecar_languages=["en"], success=True),
        success=True,
    )

    # Mock Engine
    mock_engine_instance = mock.Mock()
    mock_engine.return_value = mock_engine_instance

    txt_file = tmp_path / "Test_Title.txt"
    mock_engine_instance.convert.return_value = TranscriptResult(
        output_path=txt_file,
        output_format=TranscriptOutputFormat.TEXT,
        segment_count=10,
        title="Test Title",
    )

    execute_transcript(state, analysis_result)

    # Verify Provider Delegation
    mock_provider.download_transcript.assert_called_once()

    # Verify Engine
    mock_engine_instance.convert.assert_called_once()

    # Verify Panel summary
    mock_show_success.assert_called_once()
    panel_args = mock_show_success.call_args[0]
    assert "Transcript Completed" in panel_args[0]
    assert "Caption Source:" in panel_args[1]
    assert "Language:" in panel_args[1]
    assert "Output Format:" in panel_args[1]
    assert "Output File:" in panel_args[1]
    assert "Conversion Status:" in panel_args[1]

    # Verify Error not called
    mock_show_error.assert_not_called()


@mock.patch("mediaforge.cli.executor._get_provider")
@mock.patch("mediaforge.cli.executor.validate_download")
@mock.patch("mediaforge.cli.executor._show_error")
def test_execute_transcript_http_429(
    mock_show_error, mock_validate, mock_get_provider, state, analysis_result, tmp_path
):
    state["output_dir"] = str(tmp_path)

    mock_provider = mock.Mock()
    mock_get_provider.return_value = mock_provider
    mock_provider.download_transcript.return_value = DownloadResult(
        job_id="job123",
        url=analysis_result.url,
        status=DownloadResultStatus.COMPLETED,
        output_dir=tmp_path,
        media_type="transcript",
        files=[],
    )

    # 429 Validation
    mock_validate.return_value = DownloadValidationResult(
        subtitle=SubtitleValidationResult(
            failed_languages={"en": "HTTP 429 (Rate Limited)"}, success=False
        ),
        success=False,
    )

    execute_transcript(state, analysis_result)

    mock_show_error.assert_called_once()
    assert mock_show_error.call_args[0][0] == "Transcript temporarily unavailable."
    assert "YouTube is rate limiting" in mock_show_error.call_args[0][1]


@mock.patch("mediaforge.cli.wizard.wizards.transcript.build_transcript_wizard")
@mock.patch("mediaforge.cli.executor._get_provider")
@mock.patch("mediaforge.cli.executor.validate_download")
@mock.patch("mediaforge.cli.executor._show_error")
def test_execute_transcript_unavailable(
    mock_show_error,
    mock_validate,
    mock_get_provider,
    mock_wizard_builder,
    state,
    analysis_result,
    tmp_path,
):
    state["output_dir"] = str(tmp_path)

    mock_provider = mock.Mock()
    mock_get_provider.return_value = mock_provider
    mock_provider.download_transcript.return_value = DownloadResult(
        job_id="job123",
        url=analysis_result.url,
        status=DownloadResultStatus.COMPLETED,
        output_dir=tmp_path,
        media_type="transcript",
        files=[],
    )

    # Unavailable
    mock_validate.return_value = DownloadValidationResult(
        subtitle=SubtitleValidationResult(failed_languages={"en": "Unavailable"}, success=False),
        success=False,
    )

    mock_wizard_builder.return_value.run.return_value = None

    execute_transcript(state, analysis_result)

    mock_show_error.assert_called_once()
    assert mock_show_error.call_args[0][0] == "Transcription Not Available"
    assert (
        mock_show_error.call_args[0][1]
        == "The requested language (en) is not available.\nPlease select another language."
    )


@mock.patch("mediaforge.cli.executor._get_provider")
@mock.patch("mediaforge.cli.executor.validate_download")
@mock.patch("mediaforge.transcript.engine.TranscriptEngine")
@mock.patch("mediaforge.cli.executor._show_error")
def test_execute_transcript_failed_conversion(
    mock_show_error, mock_engine, mock_validate, mock_get_provider, state, analysis_result, tmp_path
):
    state["output_dir"] = str(tmp_path)

    mock_provider = mock.Mock()
    mock_get_provider.return_value = mock_provider

    vtt_file = tmp_path / "Test_Title.en.vtt"
    vtt_file.touch()

    mock_provider.download_transcript.return_value = DownloadResult(
        job_id="job123",
        url=analysis_result.url,
        status=DownloadResultStatus.COMPLETED,
        output_dir=tmp_path,
        media_type="transcript",
        files=[vtt_file],
    )

    mock_validate.return_value = DownloadValidationResult(
        subtitle=SubtitleValidationResult(sidecar_languages=["en"], success=True), success=True
    )

    mock_engine_instance = mock.Mock()
    mock_engine.return_value = mock_engine_instance
    mock_engine_instance.convert.side_effect = Exception("Corrupt file")

    execute_transcript(state, analysis_result)

    mock_show_error.assert_called_once()
    assert mock_show_error.call_args[0][0] == "Transcript Conversion Failed"
    assert mock_show_error.call_args[0][1] == "Corrupt file"
