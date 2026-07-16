# MediaForge

**A production-grade, zero-config YouTube media downloader for your terminal.**

MediaForge wraps the full power of [yt-dlp](https://github.com/yt-dlp/yt-dlp)
in a polished interactive CLI: paste a URL, press **1**, and get the best
possible file — same stream selection as the official yt-dlp CLI, with
subtitles, chapters, metadata, and cover art embedded automatically.

```text
 __  __          _ _       _____
|  \/  | ___  __| (_) __ _|  ___|__  _ __ __ _  ___
| |\/| |/ _ \/ _` | |/ _` | |_ / _ \| '__/ _` |/ _ \
| |  | |  __/ (_| | | (_| |  _| (_) | | | (_| |  __/
|_|  |_|\___|\__,_|_|\__,_|_|  \___/|_|  \__, |\___|
                                          |___/
```

[![CI](https://github.com/your-username/MediaForge/actions/workflows/ci.yml/badge.svg)](https://github.com/your-username/MediaForge/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/mediaforge)](https://pypi.org/project/mediaforge/)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue)](https://python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---

## Features

- ⭐ **Best Download** — one keypress, zero configuration. Selects the exact
  VP9+Opus streams (`313+251/308+251/303+251/302+251`) and merges to MKV
  without transcoding.
- 🎯 **Custom wizards** — quality, container (MP4/MKV/WebM), subtitles, audio
  format, playlists — all through guided multi-step prompts.
- 🎵 **Audio mode** — MP3, M4A, FLAC, Opus, WAV with metadata and cover art.
- 📝 **Transcripts** — download captions and convert to TXT, Markdown, or JSON.
- 💬 **Professional subtitle handling** — many languages at once; failures
  (e.g. HTTP 429) are reported per-language, never fatal.
- 🖼️ **Honest thumbnail embedding** — tells you exactly what each container
  supports instead of failing silently.
- 📊 **Rich progress + summary** — live speed/ETA, then a full report:
  resolution, FPS, HDR, codecs, bitrates, file size, subtitle outcome.
- 🩺 **`mediaforge doctor`** — one command to diagnose your environment.
- ⏯️ **Resume support** — interrupted downloads continue from `.part` files.

### Screenshot

```text
╭──────────────────── ✅ Best Download Complete ────────────────────╮
│                                                                   │
│   Video Name       Survive 30 Days Chained To A Stranger…         │
│   Channel          MrBeast                                        │
│   Container        MKV                                            │
│   Resolution       1920x1080          FPS  30 fps                 │
│   Video Codec      vp9                Video Bitrate  1490 kbps    │
│   Audio Codec      opus               Audio Bitrate  128 kbps     │
│   File Size        406.2 MB           Download Time  2m 43s       │
│                                                                   │
│   ✓ Metadata Embedded                                             │
│   ✓ Thumbnail Embedded                                            │
│      Supported by MKV container                                   │
│   ✓ Resume Supported                                              │
│                                                                   │
│   Primary Subtitle       English                                  │
│   Other Subtitles        23 languages                             │
│   Subtitles Downloaded   24                                       │
╰───────────────────────────────────────────────────────────────────╯
```

---

## Installation

```bash
pip install mediaforge
```

### Prerequisites
- **Python 3.12+**
- **yt-dlp**: Installed automatically for you when you run the `pip install` command above. No manual installation is required!

### Recommended System Tools
While MediaForge comes with fallbacks, installing these system tools ensures maximum performance and compatibility:

**1. FFmpeg (for media conversion and muxing)**
If not found, MediaForge uses a bundled fallback (`imageio-ffmpeg`), but a native installation is faster and more robust.
- **Windows:** `winget install ffmpeg` (or download from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/))
- **macOS:** `brew install ffmpeg`
- **Linux:** `sudo apt install ffmpeg` (Ubuntu/Debian)

**2. Node.js or Deno (for complex YouTube extractions)**
YouTube occasionally requires executing JavaScript to extract certain video formats.
- **Windows/macOS/Linux:** Download from [Node.js](https://nodejs.org/) or install Deno via `iwr https://deno.land/install.ps1 -useb | iex` (Windows) / `curl -fsSL https://deno.land/install.sh | sh` (macOS/Linux).

From source:

```bash
git clone https://github.com/your-username/MediaForge.git
cd MediaForge
pip install -e .
```

Verify your environment:

```bash
mediaforge doctor
```

---

## Quick Start

```bash
mediaforge
```

1. Paste a YouTube URL (video, Shorts, or playlist) and press **Enter**.
2. MediaForge analyses it and shows a menu — option **1** is always
   **⭐ Best Download**.
3. Press **1** + Enter. Done.

A live progress bar tracks the download; a summary panel reports exactly what
you got.

---

## Commands

| Command | Purpose |
|---------|---------|
| `mediaforge` | Launch the interactive app |
| `mediaforge doctor` | Diagnose environment (tools, network, YouTube access) |
| `mediaforge doctor --no-network` | Same, skipping connectivity checks |
| `mediaforge --version` | Print the version |

---

## Modes

### ⭐ Recommended (Best Download)

Zero configuration. Automatically:

| What | How |
|------|-----|
| Video | VP9 preference chain: `313+251/308+251/303+251/302+251`, then `bestvideo+bestaudio` |
| Audio | Best available track (e.g. Opus 128k) |
| Container | MKV — holds any codec, subtitles, chapters, and cover art |
| Subtitles | Manual + auto captions downloaded and embedded |
| Metadata | Title, channel, date, description embedded |
| Chapters | Embedded when the video has them |
| Thumbnail | Embedded as MKV attachment (always visible) |

### Custom video

Guided wizard: output directory → quality (Best/4K/2K/1080p/720p/480p/360p) →
container (MP4/MKV/WebM) → subtitles → confirm.

> Choosing MP4 restricts streams to MP4-compatible codecs for maximum device
> compatibility. Choose MKV for maximum quality.

### Audio

Wizard: format (MP3/M4A/FLAC/Opus/WAV) → bitrate → thumbnail → metadata.

### Transcript

Downloads captions and converts to clean TXT, Markdown, or JSON — with optional
timestamps.

### Subtitles / Thumbnail only

Direct menu actions save subtitle files or the best thumbnail without
downloading media.

---

## Configuration

MediaForge is deliberately zero-config for the common case. Power users can
tune the provider via the `YouTubeProvider(config=...)` API:

| Key | Default | Purpose |
|-----|---------|---------|
| `download_retries` | `3` | Full-download retry attempts |
| `subtitle_sleep_interval` | `1` | Seconds between subtitle requests (429 protection) |
| `ffmpeg_location` | auto | Explicit FFmpeg path |
| `metadata_cache_size` | `16` | Analyzed-URL cache entries |

Persistent user settings (config file) are on the roadmap.

---

## Dependencies

| Package | Role |
|---------|------|
| `yt-dlp` | Extraction and downloading |
| `rich` | Terminal UI |
| `curl_cffi` | Browser impersonation (reduces YouTube rate limiting) |
| `mutagen` | Visible MP4/M4A cover-art atoms |
| `webvtt-py` | Transcript parsing |
| `imageio-ffmpeg` | Bundled FFmpeg fallback |

Optional (auto-detected, recommended):

- **Deno** or **Node.js** — JS runtime for full YouTube format parity
- **AtomicParsley** — alternative MP4 cover-art writer

---

## Troubleshooting

**Run `mediaforge doctor` first.** It diagnoses nearly every common problem.

| Symptom | Cause & fix |
|---------|-------------|
| "Impersonation … not available" | `pip install curl_cffi` |
| Thumbnail invisible in Windows Explorer (MP4/M4A) | `pip install mutagen` — or use MKV. Windows Explorer ignores ffmpeg's `attached_pic`; VLC/MediaInfo show it. |
| HTTP 429 on subtitles | YouTube rate limiting. MediaForge throttles and continues; failed languages are listed in the summary. Retry later for missing ones. |
| "Some formats may be missing" | Install [Deno](https://deno.com) (or Node.js). |
| Download smaller than other tools | Modern codecs such as VP9 give the same quality in half the size of H.264. Compare resolution/codec, not bytes. |
| Interrupted download | Rerun the same download — it resumes from `.part`. |

## FAQ

**Why MKV by default?**
It's the only mainstream container that holds any codec plus subtitles,
chapters, and cover art without re-encoding — and it's what
`yt-dlp --merge-output-format mkv` produces. Choose MP4 in the custom wizard if
a device requires it.

**Is quality identical to yt-dlp?**
Best Download intentionally prefers VP9+Opus before falling back to yt-dlp's
generic bestvideo+bestaudio selector. Custom MKV downloads still use the normal
yt-dlp-style best selector.

**Does it re-encode?**
No. Streams are merged, never transcoded (except explicit audio-format
conversion in Audio mode).

**Playlists?**
Yes — Best Download and the custom wizard both support playlists with
per-item progress and failure reporting.

---

## Roadmap

- Persistent settings file (`~/.config/mediaforge/`)
- Subtitle/thumbnail embedding options in the custom wizard
- Non-interactive one-shot mode (`mediaforge <url> --best`)
- Textual full-screen TUI
- Additional providers behind the existing `Provider` ABC

---

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for setup,
quality gates, and PR guidelines. Please note the
[Code of Conduct](CODE_OF_CONDUCT.md).

```bash
pip install -e ".[dev]"
pre-commit install
pytest
```

## License

[MIT](LICENSE) © MediaForge Contributors

---

*MediaForge is an independent project built on yt-dlp. Download only content
you are authorized to access.*
