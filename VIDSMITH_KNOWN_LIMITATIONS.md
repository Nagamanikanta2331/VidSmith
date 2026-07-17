# Known Limitations

These are documented quirks and intentional behaviors of the system. Do NOT try to "fix" these unless explicitly requested.

## Windows Explorer Embedded Thumbnails
- **Symptom:** Sometimes ignores embedded thumbnails on MP4 files.
- **Cause:** Windows Explorer cache issues or atomic placement of the moov atom.
- **Verification:** If `ffprobe` shows `attached picture`, VidSmith is correct. Do not alter the architecture to fix Explorer's caching.

## YouTube's 157 Translated Subtitles
- **Symptom:** YouTube auto-generates up to 157 translated subtitles for popular videos.
- **Decision:** We intentionally filter them or rely on specific priority lists.
- **Reason:** UX. Downloading 157 VTT files clutters the UI and output directory.

## Transcript Availability
- **Symptom:** Transcript extraction fails if language is unavailable.
- **Cause:** Depends entirely on subtitle availability (manual or auto) provided by YouTube.
- **Decision:** The transcript extraction wizard now intercepts "Unavailable" languages and automatically loops back, prompting the user to select an alternative language instead of crashing. Unavailable subtitles are not errors; they are data constraints.

## Playlist Subtitle Availability Is Unknown Up Front
- **Symptom:** Playlist items request te/hi/ta/en subtitles even for videos that have none.
- **Cause:** Playlist analysis is flat (`extract_flat`) for speed — fetching per-item metadata for a 43-item playlist would multiply analysis time by the item count.
- **Decision:** Intentional. The supported set is requested blindly; `ignoreerrors=True` and the subtitle validator downgrade missing languages to "unavailable" warnings. Do not switch to per-item analysis to "fix" this.

## Private / Deleted Playlist Items Cannot Be Downloaded
- **Symptom:** Some playlist items end as "skipped: private" or "skipped: deleted" (e.g. `Completed: 39/39 available (4 skipped: 2 private, 2 deleted)`).
- **Cause:** Private videos require a signed-in account that was granted access; videos from terminated YouTube accounts no longer exist anywhere. yt-dlp itself fails identically on both (verified against real playlist items).
- **Decision:** These are classified from the yt-dlp error text (`_classify_unavailable` in `cli/executor.py`) and reported as skipped, not failed — nothing went wrong on the user's side. The only lever is the **Browser Cookies** setting (`cookies_from_browser`), which lets private videos the user's account can access download; deleted videos are unrecoverable by design. Do not retry or "fix" these.

## Playlist Parallelism Is Capped at 5
- **Symptom:** The wizard allows at most 5 simultaneous downloads.
- **Cause:** More parallel connections raise YouTube's rate-limiting/429 risk sharply and saturate most residential bandwidth anyway.
- **Decision:** Intentional cap (`_MAX_CONCURRENCY = 5` in the playlist wizard). Raise only with evidence it's safe.
