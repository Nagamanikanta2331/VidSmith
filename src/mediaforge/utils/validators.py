import re

_YOUTUBE_PATTERNS = (
    re.compile(r"https?://(?:www\.)?youtube\.com/watch\?.*v=([a-zA-Z0-9_-]{11})"),
    re.compile(r"https?://youtu\.be/([a-zA-Z0-9_-]{11})"),
    re.compile(r"https?://(?:www\.)?youtube\.com/shorts/([a-zA-Z0-9_-]{11})"),
    re.compile(r"https?://(?:www\.)?youtube\.com/playlist\?.*list=([a-zA-Z0-9_-]+)"),
    re.compile(r"https?://(?:www\.)?youtube\.com/@[\w.-]+(?:/videos)?"),
)


def is_youtube_url(url: str) -> bool:
    url = url.strip()
    return any(p.search(url) for p in _YOUTUBE_PATTERNS)


def is_shorts_url(url: str) -> bool:
    return bool(re.search(r"youtube\.com/shorts/", url.strip()))


def is_playlist_url(url: str) -> bool:
    return bool(re.search(r"[?&]list=", url.strip()))
