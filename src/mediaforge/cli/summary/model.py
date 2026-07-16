from dataclasses import dataclass, field
from enum import Enum, auto


class SummaryArtifactType(Enum):
    VIDEO = auto()
    AUDIO = auto()
    THUMBNAIL = auto()
    SUBTITLE = auto()
    TRANSCRIPT = auto()

@dataclass
class SummaryModel:
    title: str | None = None
    channel: str | None = None
    artifact_type: SummaryArtifactType = SummaryArtifactType.VIDEO

    # Standard metadata rows
    rows: list[tuple[str, str]] = field(default_factory=list)

    # Status arrays (for feature lines like Resume: Supported)
    features: list[tuple[str, str]] = field(default_factory=list)
    subtitles: list[tuple[str, str]] = field(default_factory=list)
