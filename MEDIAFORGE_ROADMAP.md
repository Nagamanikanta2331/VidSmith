# VidSmith Future Roadmap

## Phase C: Stabilization & Bug Fixes (Completed)
- [x] Triage and resolve all Open bugs in `MEDIAFORGE_BUG_TRACKER.md`.
- [x] **Subtitle Redesign:** Ensure auto, manual, and translation subtitles are fetched accurately.
- **Priority Language Groups:** Implement fallback logic for preferred languages (e.g., native -> eng -> auto).
- **Subtitle Diagnostics:** Detailed logging for subtitle extraction failures.
- **Rich Subtitle Metadata:** Embedding advanced metadata properties if possible.

## Phase D: Quality of Life & State Management
- **Download History:** Persistent SQLite or JSON database tracking downloaded media.
- **Resume Manager:** Better integration with yt-dlp's `.part` and `.ytdl` files for seamless resuming of interrupted downloads.
- **Export/Import Settings:** Allow users to share or backup their configuration profiles.

## Phase E: Extensibility
- **Plugin Architecture:** Allow community scripts for custom post-processing.
- **Multi-Provider Support:** First-class support for generic extractors outside of YouTube (e.g., Vimeo, Soundcloud, Twitch), maintaining the same Wizard-driven workflow.
