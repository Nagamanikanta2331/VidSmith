# Changelog

## [1.0.0-rc1] - 2026-07-15

MediaForge has reached its first Release Candidate! This release finalizes the core architectural refactoring and prepares the project for broader real-world testing.

### Added
- **Validation Pipeline**: Hardened the post-download validation architecture with an immutable `ValidationContext` and single-pass FFprobe inspection.
- **Windows Compatibility QA**: Introduced deterministic regression dataset generation via FFmpeg to systematically test Windows Explorer compatibility.
- **Documentation**: Added `WINDOWS_COMPATIBILITY.md`, `QA_CHECKLIST.md`, and `RELEASE_CHECKLIST.md` for standardized manual QA testing prior to releases.

### Changed
- **Audio Output & Validation**: Decoupled thumbnail generation and metadata tagging to support dynamic, safe embedding for `MP3`, `M4A`, and `FLAC` with full graceful degradation when codecs are missing.
- **Cleanup Routine**: Strengthened cleanup workflows (`test_cleanup_e2e`) to ensure temporary files (`.part`, `.webp`, `.vtt`) are accurately purged without jeopardizing the final embedded payload.
- **Subtitle and Transcript Pipelines**: Standardized subtitle download logic to perfectly integrate into the main yt-dlp job structure, guaranteeing consistent retry handling and format fallback.

### Fixed
- Fixed issues where ffmpeg crashes would improperly halt the entire validation pipeline instead of degrading gracefully.
- Removed duplicate artifacts and simplified execution paths across `YouTubeProvider`.
- Suppressed duplicate metadata injection processes.

MediaForge is now feature-complete for its 1.0.0 milestone. Future updates in the RC phase will focus solely on packaging, bug fixes, and optimization.
