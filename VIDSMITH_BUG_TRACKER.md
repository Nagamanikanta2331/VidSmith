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

### BUG-010: Validator Error Masking (Primary Output Selection)
- **Title:** When media download fails, validator inspects downloaded `.webp` thumbnail and reports misleading `Thumbnail embedding failed for ... .webp`.
- **Symptoms:** Download failures caused by YouTube bot-detection or network errors were reported to the user as thumbnail validation errors instead of missing media files.
- **Status:** Fixed
- **Root Cause:** `_get_primary_output` sorted downloaded files by size and fell back to the largest available file regardless of media type. When a video stream failed to download, only the `.webp` thumbnail existed on disk, so the validator treated the image as the primary video container and attempted to verify embedded cover art inside the `.webp` image.
- **Fix:** `_get_primary_output` now filters candidate files by valid media extensions matching `job.media_type`. If no video/audio container was written, `FileValidator` returns `FILE_MISSING` with a descriptive message. Image extensions are also excluded from thumbnail embedding verification.
- **Files:** `downloader/validator.py`, `downloader/validators/file.py`, `downloader/validators/thumbnail.py`
- **Priority:** High

### BUG-011: Forced English Subtitles & Inability to Select "No Subtitles" in Custom Playlists
- **Title:** Custom Playlist wizard forced English subtitles even when deselected, and offered no option to disable subtitles completely.
- **Symptoms:** Playlist downloads always fetched English subtitles; selecting or deselecting languages still merged `{"en"}`.
- **Status:** Fixed
- **Root Cause:** Hardcoded `| {"en"}` set union in `cli/executor.py` and missing "None" choice in `cli/wizard/wizards/playlist.py`.
- **Fix:** Added "None" choice to playlist wizard subtitle step. When "none" or an empty set is selected, `SubtitleMode.NONE` is set and language list is cleared without forcing English.
- **Files:** `cli/wizard/wizards/playlist.py`, `cli/executor.py`
- **Priority:** Medium

### BUG-012: Throttled Download Speeds (Unsolved YouTube n-challenge)
- **Title:** Extremely slow download speeds (~50KB/s) on YouTube streams.
- **Symptoms:** Downloads took 10+ minutes for small batches; yt-dlp warned about n-challenge solving failure.
- **Status:** Fixed
- **Root Cause:** Missing challenge solver script for Node.js runtime caused YouTube to intentionally throttle stream downloads.
- **Fix:** Added `"remote_components": ["ejs:github"]` and increased `concurrent_fragment_downloads` to 8 in `_safe_download_defaults()`, solving the n-challenge and enabling uncapped bandwidth.
- **Files:** `providers/youtube.py`
- **Priority:** High

### BUG-013: Video Quality Capped at 360p/720p
- **Title:** "Best" quality downloads low-resolution (360p/720p) video despite 1080p/4K being available.
- **Symptoms:** Downloaded files were 360p or 720p; 4K and 1080p streams were ignored.
- **Status:** Fixed
- **Root Cause:** Raw stream selector applied `[ext=mp4]`. Because YouTube does not serve modern high-res streams in MP4 containers (only VP9/AV1 webm), yt-dlp was forced to pick legacy low-res formats. Furthermore, mobile android client override was triggering YouTube's SABR experiment, hiding streams above 360p.
- **Fix:** Updated `_video_format_selector` to request `bestvideo+bestaudio` without raw stream container restrictions (allowing FFmpeg to remux into MP4/MKV), and removed mobile android client override.
- **Files:** `providers/youtube.py`
- **Priority:** Critical

### BUG-014: Custom Playlist Wizard Missing Thumbnail Step
- **Title:** Custom Playlist wizard did not allow users to configure thumbnail options.
- **Symptoms:** Custom playlist downloads lacked thumbnail choice and defaulted to `None`.
- **Status:** Fixed
- **Root Cause:** `build_playlist_wizard` omitted the thumbnail step, and `execute_playlist` never set `thumbnail_mode` on the template `DownloadJob`.
- **Fix:** Added `thumbnail_mode` ChoiceStep (`Embed`, `Save`, `Both`, `None`) to the wizard and wired it into `execute_playlist`.
- **Files:** `cli/wizard/wizards/playlist.py`, `cli/executor.py`
- **Priority:** Medium

### BUG-015: Post-Download Hang on Rate-Limited Subtitles in Playlists
- **Title:** Worker threads sleep for 75+ seconds after downloading media streams when YouTube returns HTTP 429 on auto-subtitles.
- **Symptoms:** Download reaches 100%, but terminal stalls for several minutes before advancing to the next batch.
- **Status:** Fixed
- **Root Cause:** `_retry_rate_limited_subtitles` executed a 5-step escalating delay ladder (5s, 10s, 15s, 20s, 25s = 75+ seconds) for all jobs, including video jobs where auto-subtitles were requested blindly.
- **Fix:** Bypassed retry ladder immediately for `DownloadMediaType.VIDEO` and `DownloadMediaType.AUDIO` jobs (`return []`). Reduced retry step and max count for dedicated subtitle jobs.
- **Files:** `providers/youtube.py`
- **Priority:** Critical

### BUG-016: Transient Sidecar Files (.vtt, .jpg) Orphaned on Disk as "Duplicates"
- **Title:** Windows Explorer shows 3 files with identical names for every downloaded video.
- **Symptoms:** Destination directory filled with raw `.jpg` thumbnails and `.vtt` subtitles alongside merged `.mp4`.
- **Status:** Fixed
- **Root Cause:** yt-dlp postprocessors were configured with `already_have_thumbnail: True` and `already_have_subtitle: True`. Additionally, in `_finalize_download`, non-fatal validation warnings on playlist items caused an early return that skipped `cleanup_job_artifacts()`.
- **Fix:** Configured yt-dlp to clean up transient sidecars upon embedding (`already_have_thumbnail: False`, `already_have_subtitle: False`). Updated `_finalize_download` to invoke `cleanup_job_artifacts()` unconditionally whenever primary media exists.
- **Files:** `providers/youtube.py`, `cli/executor.py`
- **Priority:** High

### BUG-017: Rapid Failure on Momentary Network or DNS Drops
- **Title:** Playlist downloads fail on transient DNS resolution errors (`Failed to resolve 'www.youtube.com'`).
- **Symptoms:** Items fail after momentary Wi-Fi/DNS drops because retries are exhausted in milliseconds.
- **Status:** Fixed
- **Root Cause:** Provider retry loop had zero sleep delay between attempts, immediately exhausting all 3 retries during transient network drops.
- **Fix:** Added `_is_network_error()` helper detecting DNS, socket reset, and timeout failures. Implemented exponential backoff sleep (2s, 4s, 6s) and bumped max attempts to 5 on network drops.
- **Files:** `providers/youtube.py`
- **Priority:** High

### BUG-018: Missing Resume / Skip for Already Downloaded Playlist Items
- **Title:** Re-running a playlist download repeatedly re-downloads all completed items.
- **Symptoms:** Users resuming an interrupted playlist download had to wait for already completed files to be fetched again.
- **Status:** Fixed
- **Root Cause:** `_download_item` always called `provider.download(job)` without checking whether a completed valid media file already existed in `output_dir`.
- **Fix:** Added check for existing completed media file (> 100 KB) matching the item prefix; if present, skips download in 0ms and reports `Already downloaded`.
- **Files:** `cli/executor.py`
- **Priority:** Medium


