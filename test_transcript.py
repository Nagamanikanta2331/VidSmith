import logging

from mediaforge.downloader.job import DownloadJob, DownloadMediaType, SubtitleMode
from mediaforge.providers.youtube import YouTubeProvider

logging.basicConfig(level=logging.DEBUG)


def main():
    provider = YouTubeProvider()
    job = DownloadJob(
        url="https://www.youtube.com/watch?v=BaW_CjWt5nc",  # Some video that has subtitles (like YouTube rewind or similar)
        media_type=DownloadMediaType.TRANSCRIPT,
        output_dir="C:\\MediaForge\\test_outputs",  # type: ignore
        subtitle_mode=SubtitleMode.BOTH,
        subtitle_languages=["en", "en-US", "-.*"],
    )
    result = provider.download_transcript(job)
    print(f"Result files: {result.files}")
    print(f"Failed subtitles: {result.subtitles_failed}")


if __name__ == "__main__":
    main()
