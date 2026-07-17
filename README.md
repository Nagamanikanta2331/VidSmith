# VidSmith

> **🤖 Built by AI — Idea by the Owner**
> This entire project — all source code, tests, UI, and documentation — was developed by an AI coding assistant (Claude). The original idea, product direction, and ownership belong to the repository owner, [Naga Manikanta Nandyala](https://github.com/Nagamanikanta2331).

**A production-grade, zero-config YouTube media downloader for your terminal.**

VidSmith wraps the full power of [yt-dlp](https://github.com/yt-dlp/yt-dlp)
in a polished interactive CLI: paste a URL, press **1**, and get the best
possible file — same stream selection as the official yt-dlp CLI, with
subtitles, chapters, metadata, and cover art embedded automatically.

```text
__     ___     _ ____            _ _   _
\ \   / (_) __| / ___| _ __ ___ (_) |_| |__
 \ \ / /| |/ _` \___ \| '_ ` _ \| | __| '_ \
  \ V / | | (_| |___) | | | | | | | |_| | | |
   \_/  |_|\__,_|____/|_| |_| |_|_|\__|_| |_|
```

[![CI](https://github.com/Nagamanikanta2331/VidSmith/actions/workflows/ci.yml/badge.svg)](https://github.com/Nagamanikanta2331/VidSmith/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/vidsmith)](https://pypi.org/project/vidsmith/)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue)](https://python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---

## Features

- ⭐ **Best Download** — one keypress, zero configuration. Picks the best
  available streams (VP9 preferred) and merges to MP4 without transcoding,
  with subtitles, chapters, metadata, and cover art embedded.
- 📚 **Playlists — parallel & complete** — download entire playlists (or a
  custom range) with **up to 5 items downloading simultaneously**, per-item
  subtitles embedded, live progress, and honest completed/failed/warning
  reporting.
- 📱 **Shorts** — paste a `youtube.com/shorts/...` link and it just works:
  same menu, same embedding, vertical video handled natively.
- 🎯 **Custom wizards** — quality, container (MP4/MKV/WebM), subtitles, audio
  format, playlists — all through guided multi-step prompts.
- 💬 **Professional subtitle handling** — Telugu, Hindi, Tamil, and English
  (manual preferred over auto-generated) requested for every download,
  including each playlist item; missing languages are skipped silently and
  failures (e.g. HTTP 429) are reported per-language, never fatal.
- 🎵 **Audio mode** — MP3, M4A, FLAC, Opus, WAV with metadata and cover art.
- 📝 **Transcripts** — download captions and convert to TXT, Markdown, or JSON.
- 🖼️ **Honest thumbnail embedding** — tells you exactly what each container
  supports instead of failing silently.
- 📊 **Rich progress + summary** — live speed/ETA, then a full report:
  resolution, FPS, HDR, codecs, bitrates, file size, per-language subtitle
  outcome.
- ⏩ **Continue-or-switch prompt** — after every download: press Enter to keep
  working with the same video, `n` to paste a new URL, `q` to quit.
- 🩺 **`vidsmith doctor`** — one command to diagnose your environment.
- ⏯️ **Resume support** — interrupted downloads continue from `.part` files.

### Screenshot

```text
╭──────────────────── ✓ Best Download Complete ─────────────────────╮
│                                                                   │
│   Video Name             Survive 30 Days Chained To A Stranger…   │
│   Channel                MrBeast                                  │
│   Container              MP4                                      │
│   Resolution             1920x1080       FPS  30 fps              │
│   Video Codec            vp9             Video Bitrate  1490 kbps │
│   Audio Codec            mp4a.40.2       Audio Bitrate  130 kbps  │
│   File Size              406.2 MB        Download Time  2m 43s    │
│                                                                   │
│   Metadata               ✓ Embedded                               │
│   Thumbnail              ✓ Embedded                               │
│   Resume                 ✓ Supported                              │
│   Telugu (te) Subtitle   ✓ Embedded                               │
│   Hindi (hi) Subtitle    ✓ Embedded                               │
│   Tamil (ta) Subtitle    ✓ Embedded                               │
│   English (en) Subtitle  ✓ Embedded                               │
╰───────────────────────────────────────────────────────────────────╯
```

---

## Installation

```bash
pip install vidsmith
```

Or install the latest development version from GitHub:

```bash
pip install git+https://github.com/Nagamanikanta2331/VidSmith.git
```

Or clone and install from source:

```bash
git clone https://github.com/Nagamanikanta2331/VidSmith.git
cd VidSmith
pip install -e .
```

### Updating

Get the newest release from PyPI (using `--no-cache-dir` ensures pip doesn't use a stale cached version):

```bash
pip install --upgrade --no-cache-dir vidsmith
```

Or update straight from GitHub (picks up changes as soon as they are pushed,
without waiting for a PyPI release):

```bash
pip install --upgrade --force-reinstall --no-deps git+https://github.com/Nagamanikanta2331/VidSmith.git
```

Check your installed version anytime:

```bash
vidsmith --version
```

### Uninstalling

```bash
pip uninstall vidsmith
```

This removes the package and the `vidsmith` command. Your downloaded media is
never touched. To also remove saved settings and logs, delete the config
folder: `%APPDATA%\VidSmith` on Windows, or `~/.config/vidsmith` on
Linux/macOS.

### Prerequisites
- **Python 3.12+**
- **yt-dlp**: Installed automatically for you when you run the installation command above. No manual installation is required!

### Recommended System Tools
While VidSmith comes with fallbacks, installing these system tools ensures maximum performance and compatibility:

**1. FFmpeg (for media conversion and muxing)**
If not found, VidSmith uses a bundled fallback (`imageio-ffmpeg`), but a native installation is faster and more robust.
- **Windows:** `winget install ffmpeg` (or download from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/))
- **macOS:** `brew install ffmpeg`
- **Linux:** `sudo apt install ffmpeg` (Ubuntu/Debian)

**2. Node.js or Deno (for complex YouTube extractions)**
YouTube occasionally requires executing JavaScript to extract certain video formats.
- **Windows/macOS/Linux:** Download from [Node.js](https://nodejs.org/) or install Deno via `iwr https://deno.land/install.ps1 -useb | iex` (Windows) / `curl -fsSL https://deno.land/install.sh | sh` (macOS/Linux).

Verify your environment:

```bash
vidsmith doctor
```

---

## Quick Start

```bash
vidsmith
```

1. Paste a YouTube URL (video, Shorts, or playlist) and press **Enter**.
2. VidSmith analyses it and shows a menu — option **1** is always
   **⭐ Best Download**.
3. Press **1** + Enter. Done.

A live progress bar tracks the download; a summary panel reports exactly what
you got.

---

## Commands

| Command | Purpose |
|---------|---------|
| `vidsmith` | Launch the interactive app |
| `vidsmith doctor` | Diagnose environment (tools, network, YouTube access) |
| `vidsmith doctor --no-network` | Same, skipping connectivity checks |
| `vidsmith --version` | Print the version |
| `pip install --upgrade --no-cache-dir vidsmith` | Update to the latest release |
| `pip uninstall vidsmith` | Remove VidSmith |

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

### Playlists

Paste a playlist URL and the menu switches to playlist actions:

- **⭐ Best Download** — every item gets the full Best Download treatment
  (best streams, MP4, subtitles, thumbnail, metadata, chapters), downloading
  **several items in parallel** (your `max_concurrency` setting, default 3).
- **Custom Playlist Download** — guided wizard: item selection (all / range
  like `1-10` / specific items) → video or audio → quality → **subtitles**
  (Telugu/Hindi/Tamil/English multi-select; English is always included as a
  mandatory fallback) → output directory → **parallel downloads (1–5)** →
  confirm.
- **Audio / subtitles / thumbnails for the whole playlist** — dedicated menu
  entries.

The summary panel reports completed/failed counts honestly: an item whose
media downloaded fine but whose thumbnail or subtitle embed check failed is
counted as **completed with a warning**, never as a failed download — and
failure reasons are shown in full, not truncated into uselessness.

Videos nobody could download — private videos and videos whose channel was
deleted — are **not counted as failures** either. They show up as skipped,
with the reason: `Completed: 39/39 available (4 skipped: 2 private, 2
deleted)`. If your YouTube account actually has access to a private video,
enable **Browser Cookies** in Settings and it will download.

### Shorts

YouTube Shorts URLs (`youtube.com/shorts/...`) are fully supported — paste
one and you get the same menu and the same treatment as a regular video:
best streams (AV1/VP9 vertical), embedded subtitles in all supported
languages, thumbnail, and metadata.

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

VidSmith is deliberately zero-config for the common case. Power users can
tune the provider via the `YouTubeProvider(config=...)` API:

| Key | Default | Purpose |
|-----|---------|---------|
| `download_retries` | `3` | Full-download retry attempts |
| `subtitle_sleep_interval` | `1` | Seconds between subtitle requests (429 protection) |
| `ffmpeg_location` | auto | Explicit FFmpeg path |
| `metadata_cache_size` | `16` | Analyzed-URL cache entries |
| `cookies_from_browser` | off | Browser to import YouTube cookies from (enables private videos you have access to) |

Persistent user settings live in the in-app **Settings** menu (press `s`):
default quality, audio format, output directory, parallel downloads
(`max_concurrency`), cleanup behavior, **browser cookies** (for private
videos your account can access), and more — saved to the `VidSmith`
config directory automatically.

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

**Run `vidsmith doctor` first.** It diagnoses nearly every common problem.

| Symptom | Cause & fix |
|---------|-------------|
| "Impersonation … not available" | `pip install curl_cffi` |
| Thumbnail invisible in Windows Explorer (MP4/M4A) | `pip install mutagen` — or use MKV. Windows Explorer ignores ffmpeg's `attached_pic`; VLC/MediaInfo show it. |
| HTTP 429 on subtitles | YouTube rate limiting. VidSmith throttles and continues; failed languages are listed in the summary. Retry later for missing ones. |
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
Yes — Best Download and the custom wizard both support playlists, with items
downloading **in parallel** (up to 5 at a time), per-item subtitle embedding,
live progress, and honest per-item failure/warning reporting. Shorts links
work too.

---

## Roadmap

- Subtitle/thumbnail embedding options in the custom video wizard
- Non-interactive one-shot mode (`vidsmith <url> --best`)
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

[MIT](LICENSE) © Naga Manikanta Nandyala

---

*VidSmith is an independent project built on yt-dlp. Download only content
you are authorized to access.*
