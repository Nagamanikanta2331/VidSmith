# MediaForge Bug Tracker

## 1. Current Implementation Status

| Feature | Status | Notes |
|---|---|---|
| Audio | ✅ | Functional and validated. |
| Metadata | ✅ | Tagging and embedding works. |
| Chapters | ✅ | Enabled by default. |
| Thumbnail | ✅ | Writes and embeds correctly. |
| Transcript | ✅ | Fixed (Language code resolved). |
| Subtitle Only | ✅ | Fixed (Enum mapped properly). |
| Thumbnail Only | ✅ | Fixed (Enum mapped properly). |
| Custom Video | ✅ | Functional and validated. |
| Best Download | ✅ | Functional and validated. |

## 2. Known Bugs

### BUG-001: String/Int Comparison Crash
- **Title:** Best Download / Custom Video crashes during format filtering.
- **Symptoms:** `TypeError: '<=' not supported between instances of 'str' and 'int'`
- **Status:** Fixed
- **Root Cause:** Format height was evaluated as a string instead of an int during config resolution.
- **Files:** `executor.py` / `provider` logic
- **Priority:** Critical

### BUG-002: Subtitle Validator Mismatch
- **Title:** Subtitle downloads are validated incorrectly.
- **Symptoms:** Subtitle flow uses the Transcript Validator instead of the Subtitle Validator.
- **Status:** Fixed
- **Root Cause:** Wrong validator instantiated in the factory or execution pipeline.
- **Files:** `validator.py`, `executor.py`
- **Priority:** High

### BUG-003: Thumbnail Validator Mismatch
- **Title:** Thumbnail downloads are validated incorrectly.
- **Symptoms:** Thumbnail flow uses the Transcript Validator.
- **Status:** Fixed
- **Root Cause:** Copy-paste error or mapping issue in execution pipeline.
- **Files:** `validator.py`, `executor.py`
- **Priority:** High

### BUG-004: Transcript Unavailable Error
- **Title:** Transcripts fail to extract despite available subs.
- **Symptoms:** Output shows "Unavailable" even when 157 auto-subtitles are detected by the Metadata Analyzer.
- **Status:** Fixed
- **Root Cause:** Unknown. Could be a missing argument (e.g. `--write-auto-subs`) or format conversion failure (`vtt`).
- **Files:** `transcript.py`, yt-dlp arguments
- **Priority:** Medium

### BUG-005: Embedded Cover Art Not Displaying
- **Title:** Windows Explorer doesn't show embedded cover art for some MP4s.
- **Symptoms:** The file has `attached picture` in `ffprobe`, but Explorer displays a generic icon.
- **Status:** Fixed
- **Root Cause:** Solved by utilizing `mutagen` for proper atomic placement in M4A/MP4 formats.
- **Files:** yt-dlp arguments, post-processors
- **Priority:** Low
