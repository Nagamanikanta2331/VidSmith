# Known Limitations

These are documented quirks and intentional behaviors of the system. Do NOT try to "fix" these unless explicitly requested.

## Windows Explorer Embedded Thumbnails
- **Symptom:** Sometimes ignores embedded thumbnails on MP4 files.
- **Cause:** Windows Explorer cache issues or atomic placement of the moov atom.
- **Verification:** If `ffprobe` shows `attached picture`, MediaForge is correct. Do not alter the architecture to fix Explorer's caching.

## YouTube's 157 Translated Subtitles
- **Symptom:** YouTube auto-generates up to 157 translated subtitles for popular videos.
- **Decision:** We intentionally filter them or rely on specific priority lists.
- **Reason:** UX. Downloading 157 VTT files clutters the UI and output directory.

## Transcript Availability
- **Symptom:** Transcript extraction fails if language is unavailable.
- **Cause:** Depends entirely on subtitle availability (manual or auto) provided by YouTube.
- **Decision:** The transcript extraction wizard now intercepts "Unavailable" languages and automatically loops back, prompting the user to select an alternative language instead of crashing. Unavailable subtitles are not errors; they are data constraints.
