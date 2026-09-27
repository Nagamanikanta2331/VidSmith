# Changelog

## [1.2.0] - 2026-09-25

### Added
- **Uncapped Best Quality (up to 4K / 8K):** Completely removed legacy `[ext=mp4]` stream filtering that was restricting YouTube downloads to low-resolution (360p/720p) formats. VidSmith now fetches the true highest available video and audio streams (4K, 1440p, 1080p, 720p) and remuxes them into the desired container using FFmpeg without transcoding.
- **Uncapped Download Speeds (`n`-challenge solver):** Integrated automatic EJS challenge solving (`remote_components: ["ejs:github"]`) powered by Node.js. This eliminates YouTube's 50KB/s download speed throttling, allowing full-bandwidth downloads. Increased concurrent fragment downloads to 8.
- **Thumbnail Options for Custom Playlists:** Added a dedicated Thumbnail step to the Custom Playlist wizard offering `Embed into video`, `Save separately`, `Both (Embed & Save)`, and `None`.
- **Persistent Cookie File Support (`cookies.txt`):** Added a persistent `cookie_file` setting (Settings → Cookie File (cookies.txt)) allowing users to supply an exported Netscape-format `cookies.txt` file once. This permanently bypasses YouTube bot checks ("Sign in to confirm you're not a bot") and age-verification gates without triggering Windows DPAPI decryption errors. Includes in-app instructions and Chrome Web Store extension link (`Get cookies.txt LOCALLY`).
- **"None" Subtitle Option for Custom Playlists:** Added a clear "None (No Subtitles)" choice to the Custom Playlist wizard. Deselecting subtitles or selecting None cleanly disables subtitles and downloads playlist items without subtitle sidecars or embedded text.
- **Smart Playlist Resume:** Added intelligent detection of already-downloaded completed media files in the destination directory, instantly skipping them in 0ms so users never re-download existing media when resuming playlists.
- **Automatic Network & DNS Drop Recovery:** Added automatic detection of transient network and DNS drops (`Failed to resolve 'www.youtube.com'`, socket timeouts, connection resets). VidSmith now pauses with exponential backoff across up to 5 attempts, allowing momentary Wi-Fi/DNS drops to recover seamlessly.
- **Live Merging Status Indicator:** Added real-time progress updates displaying `Merging…` during FFmpeg stream muxing and metadata embedding before clearing completed items from the live task display.

### Fixed
- **Resolved False Thumbnail Validation Masking Real Failures:** Fixed primary output resolution in the download validator. When a video stream failed to download (e.g. from network or authentication errors), the validator previously fell back to the downloaded `.webp` thumbnail and misleadingly reported `Thumbnail embedding failed`. The validator now verifies the existence of valid video/audio containers matching the job media type before running inspection steps.
- **Removed Hardcoded Forced English Subtitles in Playlists:** Removed the hardcoded `| {"en"}` set union in the playlist execution pipeline, respecting user subtitle choices exactly.
- **Immediate Sidecar Deletion & Duplicate Prevention:** Ensured that transient scaffolding files (`.jpg`, `.vtt`, `.part`, `.temp`) are deleted in milliseconds after media embedding, leaving only the clean final media file. Configured yt-dlp's `FFmpegEmbedSubtitle` and `EmbedThumbnail` postprocessors to automatically clean up sidecars after embedding, and made `_finalize_download` run cleanup unconditionally for completed media.
- **Eliminated Post-Download Subtitle Hang (75s delay):** Bypassed the escalating retry ladder for video/audio downloads when YouTube returns HTTP 429 on auto-captions. Videos merge and finish immediately without stalling the worker pool.
- **DownloadStage Enum Compatibility:** Added `PROCESSING_METADATA` and `PROCESSING_THUMBNAIL` backwards-compatible aliases to `DownloadStage`.

## [1.1.2] - 2026-07-17

### Added
- **Browser Cookies setting** (Settings → Browser Cookies, off by default). Imports YouTube cookies from Chrome/Edge/Firefox/Brave/Opera/Vivaldi (yt-dlp's `--cookies-from-browser`) so private videos the signed-in account has access to can be analyzed and downloaded. When off — the default — nothing changes.

### Changed
- **Playlist summaries no longer count unavailable videos as failures.** Private videos and videos whose YouTube channel was terminated cannot be downloaded by anyone; they are now classified from the yt-dlp error text and reported as skipped with a reason — `Completed: 39/39 available (4 skipped: 2 private, 2 deleted)` — instead of `Completed: 39/43, Failed: 4`. The red "Failures" list and the "(N failed)" panel title now appear only for real failures. Applies to both Best Download and Custom Playlist paths.

### Fixed
- `__version__` in the `vidsmith` package was stuck at `0.1.0`; it now matches the release version.

## [1.1.1] - 2026-07-17

### Fixed
- Fixed the `--version` CLI flag printing `1.0.0` instead of the actual installed version (forgotten hardcoded version bump in `APP_VERSION`).

## [1.1.0] - 2026-07-16

Playlist speed and completeness release. Update with `pip install --upgrade vidsmith`.

### Added
- **Parallel playlist downloads.** Playlist items now actually download simultaneously — Best Download uses the `max_concurrency` setting (default 3), and Custom Playlist honors the wizard's "Parallel Downloads" answer (previously collected but ignored; items always downloaded one at a time). Each worker uses its own yt-dlp instance; per-item behavior is unchanged.
- **Subtitle step in the Custom Playlist wizard.** Choose from Telugu / Hindi / Tamil / English (all pre-selected). English is a mandatory fallback: it is always requested even when deselected, so every item gets at least the auto-generated English track merged when one exists.
- **Post-download prompt.** After any download completes, the app now asks whether to continue with the current video (Enter), download another video (`n` → URL prompt), or quit (`q`) — instead of silently returning to the same video's menu.

### Fixed
- **Playlist downloads now include subtitles.** Both Best Download and Custom Playlist video items request the supported subtitle set (te/hi/ta/en, manual over auto) and embed whatever exists; unavailable languages are skipped silently.
- **Playlist failure counting.** Items whose media downloaded fine but failed a post-processing check (e.g. thumbnail embedding) are no longer counted as failed downloads — they complete and are listed under "Warnings (media saved, embed check failed)".
- **Playlist failure messages.** The constant "download failed after N attempts:" prefix is stripped and the visible reason budget raised from 80 to 160 characters, so the actual yt-dlp error is readable in the summary panel.

### Documentation
- README: playlist and Shorts feature sections, updated screenshot, update/uninstall instructions.

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
