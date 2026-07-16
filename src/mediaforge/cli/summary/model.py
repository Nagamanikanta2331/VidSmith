from dataclasses import dataclass


@dataclass
class SummaryModel:
    title: str | None = None
    container: str | None = None
    output_folder: str | None = None
    file_name: str | None = None
    file_size_bytes: int | None = None
    duration_seconds: int | None = None
    download_seconds: float | None = None
    channel: str | None = None

    # Video details
    video_quality: str | None = None
    resolution: str | None = None
    fps: str | None = None
    hdr: str | None = None
    video_codec: str | None = None
    video_bitrate: str | None = None

    # Audio details
    audio_codec: str | None = None
    audio_bitrate: str | None = None
    audio_language: str | None = None

    # Status arrays (for feature lines like Resume: Supported)
    features: list[tuple[str, str]] = None
    subtitles: list[tuple[str, str]] = None

    def __post_init__(self):
        if self.features is None:
            self.features = []
        if self.subtitles is None:
            self.subtitles = []
