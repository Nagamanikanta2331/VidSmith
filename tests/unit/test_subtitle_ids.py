from pathlib import Path

import pytest

from mediaforge.downloader.job import DownloadJob, DownloadMediaType, SubtitleMode
from mediaforge.providers.youtube import YouTubeProvider
from mediaforge.subtitle import resolve_subtitle_selection


@pytest.mark.parametrize(
    "exact_id",
    [
        "en",
        "hi-IN",
        "en-US",
        "te",
        "fr",
    ],
)
def test_subtitle_id_passed_exactly_through_pipeline(exact_id):
    # 1. Test resolve_subtitle_selection (simulates job builder resolving available tracks)
    # Assume the exact id is available in manual tracks
    selection = resolve_subtitle_selection(
        manual_codes=[exact_id], auto_codes=[], requested=[exact_id]
    )

    assert exact_id in selection.codes
    assert exact_id in selection.requested

    # 2. Test provider options generation
    job = DownloadJob(
        url="https://youtube.com/watch?v=123",
        media_type=DownloadMediaType.VIDEO,
        output_dir=Path("/tmp/dummy"),
        subtitle_mode=SubtitleMode.MANUAL,
        subtitle_languages=selection.codes,
    )

    provider = YouTubeProvider()

    # We can access _subtitle_languages directly, which yt-dlp consumes via subtitleslangs
    langs = provider._subtitle_languages(job)

    # No transformation anywhere!
    assert exact_id in langs
    assert langs == [exact_id]
