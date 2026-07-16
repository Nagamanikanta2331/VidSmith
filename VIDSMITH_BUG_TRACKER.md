# VidSmith Bug Tracker

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

### BUG-006: UnicodeDecodeError in Subprocess Reader Thread (Windows)
- **Title:** Intermittent `UnicodeDecodeError: 'charmap' codec can't decode byte …` after downloads.
- **Symptoms:** A traceback from `threading` / `subprocess._readerthread` printed mid-UI when downloading videos whose metadata contains non-ASCII characters (Hindi titles, fullwidth `｜`, emoji). Download itself completed fine.
- **Status:** Fixed
- **Root Cause:** `subprocess.run(..., text=True)` without an explicit `encoding` decodes child output using the Windows ANSI codepage (cp1252), while ffprobe/ffmpeg emit UTF-8. Bytes like `0x8d` have no cp1252 mapping and crash the reader thread.
- **Fix:** Added `encoding="utf-8", errors="replace"` to every captured-output subprocess call (`validators/context.py`, `providers/youtube.py`, `processing/ffmpeg.py`, `utils/environment.py`).
- **Priority:** Medium

### BUG-007: Playlist Downloads Skip Subtitles
- **Title:** Neither playlist path downloads or embeds subtitles.
- **Symptoms:** Playlist test run (43 items) completed with zero subtitle files/streams, while single-video Best Download embeds them. Reported from user playlist testing on 2026-07-16.
- **Status:** Fixed
- **Root Cause:** Playlist analysis is flat (`extract_flat`), so per-item caption availability is unknown; `_best_video_job` resolved subtitles to `NONE` for playlist items, and the custom-playlist `download_template` never set subtitle fields.
- **Fix:** New `_blind_subtitle_selection()` requests the full supported set (te/hi/ta/en) with `SubtitleMode.BOTH` for playlist video items in both paths. `ignoreerrors=True` + the subtitle validator already treat unavailable languages as non-fatal warnings.
- **Files:** `cli/executor.py` (`_best_video_job`, `execute_playlist`)
- **Priority:** High

### BUG-008: Playlist Items Counted as Failed on Embed-Check Warnings
- **Title:** "Thumbnail embedding failed" validation counts a fully-downloaded item as a failed download.
- **Symptoms:** Playlist summary showed "5 failed" where one item's MP4 downloaded fine but its thumbnail didn't embed. Real failure reasons were also unreadable — truncated at 80 chars, with the constant retry prefix eating the budget.
- **Status:** Fixed
- **Root Cause:** `_finalize_download` raised `DownloadError` on ANY validation failure; playlist loops caught every exception as a failed item. Summary lines used `err[:80]`.
- **Fix:** `_finalize_download(strict=False)` for playlist items — only `FILE_MISSING`/`FILE_EMPTY` still raise; embed-check failures return the validation and are reported under "Warnings (media saved, embed check failed)". New `_format_item_error()` strips the retry prefix and keeps 160 chars of the actual reason. Single-video behavior unchanged (`strict=True` default).
- **Files:** `cli/executor.py` (`_finalize_download`, `execute_best_playlist_download`, `_run_queued`)
- **Priority:** High

### BUG-009: Playlist Downloads Serial Despite "Parallel Downloads" Setting
- **Title:** The wizard's "Parallel Downloads: N" answer was collected but never used; all playlist items downloaded one at a time.
- **Symptoms:** 43-item playlist took ~43× single-item time regardless of the concurrency chosen in the wizard. Reported from user playlist testing on 2026-07-16.
- **Status:** Fixed
- **Root Cause:** Both playlist loops (`execute_best_playlist_download`, `_run_queued`) were sequential `for`/`while` loops; the `concurrency` wizard key and `AppSettings.max_concurrency` were never read by any download path.
- **Fix:** Both paths now run items through a `ThreadPoolExecutor` — Best Download sized by `max_concurrency` (default 3), Custom Playlist by the wizard answer (1–5). Each worker constructs its own `YoutubeDL`, so no yt-dlp state is shared; results/warnings/errors are aggregated in the main thread.
- **Files:** `cli/executor.py` (`execute_best_playlist_download`, `_run_queued`, `execute_playlist`)
- **Priority:** High
