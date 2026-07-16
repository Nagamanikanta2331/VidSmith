"""User-level settings (persistent config).

``AppSettings`` is the typed settings surface. Persistence lives in
``settings.store`` (JSON on disk); this module holds the dataclass and the
process-wide instance every consumer reads.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class AppSettings:
    # Existing preferences (kept for the pre-Phase-B wizard fields).
    default_output_dir: Path = field(default_factory=lambda: Path("~/Downloads").expanduser())
    default_quality: str = "best"
    default_audio_format: str = "mp3"
    default_audio_quality: str = "192k"
    max_concurrency: int = 3

    # Phase B additions.
    default_output_directory: str = ""  # "" → fall back to ~/Downloads
    default_container: str = "mp4"  # mp4 | mkv | webm
    subtitle_delay_seconds: int = 0
    cleanup_enabled: bool = True
    keep_temp_files: bool = False
    node_path_override: str = ""
    ffmpeg_path_override: str = ""
    debug_logging: bool = False


# Module-level default instance
settings = AppSettings()
