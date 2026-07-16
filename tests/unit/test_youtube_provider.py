"""Unit tests for pure logic in YouTubeProvider (no network access)."""

from __future__ import annotations

from mediaforge.providers.youtube import (
    YouTubeProvider,
    _classify_subtitle_reason,
    _SubtitleLogger,
)


class TestVideoFormatSelector:
    def setup_method(self) -> None:
        self.provider = YouTubeProvider()

    def test_best_uses_vp9_preference_chain(self) -> None:
        """Best quality uses the shared VP9+Opus preference before generic fallback."""
        assert self.provider._video_format_selector("best", "mkv") == (
            "313+251/308+251/303+251/302+251/bestvideo+bestaudio"
        )

    def test_height_capped_mkv(self) -> None:
        selector = self.provider._video_format_selector("1080", "mkv")
        assert selector == "303+251/302+251/bv*[height<=1080]+ba/b[height<=1080]"

    def test_mp4_uses_vp9_preference_before_compatibility_filters(self) -> None:
        selector = self.provider._video_format_selector("best", "mp4")
        assert selector.startswith("313+251/308+251/303+251/302+251/")
        assert "[ext=mp4]" in selector
        assert "[ext=m4a]" in selector

    def test_unknown_quality_falls_back_to_best(self) -> None:
        assert self.provider._video_format_selector("weird", "mkv") == (
            "313+251/308+251/303+251/302+251/bestvideo+bestaudio"
        )


class TestSubtitleFailureCapture:
    def test_classifies_http_429(self) -> None:
        assert _classify_subtitle_reason("HTTP Error 429: Too Many Requests") == (
            "HTTP 429 (Rate Limited)"
        )

    def test_classifies_unavailable(self) -> None:
        assert _classify_subtitle_reason("HTTP Error 404: Not Found") == "Unavailable"

    def test_classifies_unknown(self) -> None:
        assert _classify_subtitle_reason("") == "Unknown"

    def test_logger_records_language_and_reason(self) -> None:
        logger = _SubtitleLogger()
        logger.warning(
            "Unable to download video subtitles for 'ar': HTTP Error 429: Too Many Requests"
        )
        assert logger.subtitle_failures == {"ar": "HTTP 429 (Rate Limited)"}

    def test_logger_ignores_unrelated_warnings(self) -> None:
        logger = _SubtitleLogger()
        logger.warning("Some unrelated warning about formats")
        assert logger.subtitle_failures == {}


class TestResultMetadata:
    def setup_method(self) -> None:
        self.provider = YouTubeProvider()

    def test_prefers_requested_formats_streams(self) -> None:
        info = {
            "title": "Video",
            "channel": "Chan",
            "ext": "mkv",
            "requested_formats": [
                {
                    "vcodec": "av01.0.08M.08",
                    "acodec": "none",
                    "height": 1080,
                    "width": 1920,
                    "vbr": 1490.0,
                    "fps": 30,
                },
                {"vcodec": "none", "acodec": "opus", "abr": 128.0, "language": "en"},
            ],
        }
        metadata = self.provider._result_metadata(info)
        assert metadata["video_codec"] == "av01.0.08M.08"
        assert metadata["audio_codec"] == "opus"
        assert metadata["audio_bitrate"] == "128 kbps"
        assert metadata["fps"] == "30 fps"
        assert metadata["title"] == "Video"
        assert metadata["channel"] == "Chan"

    def test_omits_empty_fields(self) -> None:
        metadata = self.provider._result_metadata({"ext": "mkv"})
        assert "hdr" not in metadata
        assert "audio_bitrate" not in metadata

class TestNormalization:
    def setup_method(self) -> None:
        self.provider = YouTubeProvider()

    def test_container_normalization(self) -> None:
        assert self.provider._normalized_video_container("MKV") == "mkv"
        assert self.provider._normalized_video_container("nonsense") == "mp4"

    def test_quality_height(self) -> None:
        assert self.provider._quality_height("1080p") == 1080
        assert self.provider._quality_height("best") is None
        assert self.provider._quality_height("999") == 999
