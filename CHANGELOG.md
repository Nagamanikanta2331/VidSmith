# Changelog

## [Unreleased]

### Added
- **Post-download prompt.** After any download completes, the app now asks whether to continue with the current video (Enter), download another video (`n` → URL prompt), or quit (`q`) — instead of silently returning to the same video's menu.

### Fixed
- **Playlist downloads now include subtitles.** Both Best Download and Custom Playlist video items request the supported subtitle set (te/hi/ta/en, manual over auto) and embed whatever exists; unavailable languages are skipped silently.
- **Playlist failure counting.** Items whose media downloaded fine but failed a post-processing check (e.g. thumbnail embedding) are no longer counted as failed downloads — they complete and are listed under "Warnings (media saved, embed check failed)".
- **Playlist failure messages.** The constant "download failed after N attempts:" prefix is stripped and the visible reason budget raised from 80 to 160 characters, so the actual yt-dlp error is readable in the summary panel.

## [1.0.0] - 2026-07-16

First stable release — published to [PyPI](https://pypi.org/project/vidsmith/): `pip install vidsmith`.

### Changed
- **Project renamed: MediaForge → VidSmith.** The previous name collided with an existing PyPI package. The distribution, import package (`vidsmith`), and terminal command (`vidsmith`) are all renamed; the on-screen logo and product name are rebranded. Functionality and behavior are unchanged.
- Settings are now stored under the `VidSmith` config directory. Existing settings from a previous MediaForge install are automatically copied over on first launch — no reconfiguration needed.
- Debug logs now write to `vidsmith.log` in the `VidSmith` config directory.
- Repository moved to [Nagamanikanta2331/VidSmith](https://github.com/Nagamanikanta2331/VidSmith); all project links updated.

### Fixed
- Fixed an intermittent `UnicodeDecodeError` (`'charmap' codec can't decode byte …`) on Windows during post-download validation. Subprocess output from ffmpeg/ffprobe was being decoded with the legacy ANSI codepage (cp1252) instead of UTF-8, crashing the reader thread when video metadata contained non-ASCII characters (e.g. Hindi titles, fullwidth `｜`, emoji). All captured-output subprocess calls now decode as UTF-8 with `errors="replace"`.

## [1.0.0-rc1] - 2026-07-15

VidSmith has reached its first Release Candidate! This release finalizes the core architectural refactoring and prepares the project for broader real-world testing.

### Added
- **Validation Pipeline**: Hardened the post-download validation architecture with an immutable `ValidationContext` and single-pass FFprobe inspection.
- **Windows Compatibility QA**: Introduced deterministic regression dataset generation via FFmpeg to systematically test Windows Explorer compatibility.
- **Documentation**: Added `WINDOWS_COMPATIBILITY.md`, `QA_CHECKLIST.md`, and `RELEASE_CHECKLIST.md` for standardized manual QA testing prior to releases.

### Changed
- **Audio Output & Validation**: Decoupled thumbnail generation and metadata tagging to support dynamic, safe embedding for `MP3`, `M4A`, and `FLAC` with full graceful degradation when codecs are missing.
- **Cleanup Routine**: Strengthened cleanup workflows (`test_cleanup_e2e`) to ensure temporary files (`.part`, `.webp`, `.vtt`) are accurately purged without jeopardizing the final embedded payload.
- **Subtitle and Transcript Pipelines**: Standardized subtitle download logic to perfectly integrate into the main yt-dlp job structure, guaranteeing consistent retry handling and format fallback.
- **Transcript UX**: Improved the transcript extraction workflow to gracefully notify the user and restart the wizard if a selected language is unavailable, preventing abrupt exits.
- **Documentation**: Updated `README.md` with explicit, platform-specific installation instructions for FFmpeg and Node.js/Deno, and clarified that `yt-dlp` is automatically installed.

### Fixed
- Fixed issues where ffmpeg crashes would improperly halt the entire validation pipeline instead of degrading gracefully.
- Removed duplicate artifacts and simplified execution paths across `YouTubeProvider`.
- Suppressed duplicate metadata injection processes.
- Fixed a critical `TypeError` string/int comparison bug in Best Download and Custom Video formats filtering.

VidSmith is now feature-complete for its 1.0.0 milestone. Future updates in the RC phase will focus solely on packaging, bug fixes, and optimization.
