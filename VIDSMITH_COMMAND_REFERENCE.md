# yt-dlp Command Reference

All generated options MUST match these "GOLDEN COMMAND" templates.

## ⭐ GOLDEN COMMAND: Best Download (Production Reference)
```bash
yt-dlp ^
--cookies-from-browser chrome ^
--js-runtimes node ^
-f "bv*+ba/b" ^
--merge-output-format mp4 ^
--write-auto-subs ^
--sub-langs "te,hi,ta,ml,kn,bn,gu,mr,pa,or,as,ur,sa,en,en-orig,-live_chat,.*" ^
--embed-subs ^
--write-thumbnail ^
--embed-thumbnail ^
--convert-thumbnails jpg ^
--add-metadata ^
--ignore-errors ^
-P OUTPUT_DIRECTORY ^
VIDEO_URL
```
**Flags Explained:**
- `--cookies-from-browser chrome`: Bypasses age restrictions/auth.
- `-f "bv*+ba/b"`: Selects best video and best audio, falling back to best combined.
- `--sub-langs "..."`: Priority list for embedded subtitles.

## 🎥 Custom Video Download
```bash
yt-dlp ^
--cookies-from-browser chrome ^
--js-runtimes node ^
-f "bestvideo[height<=2160]+bestaudio/best[height<=2160]" ^
--merge-output-format mp4 ^
--write-auto-subs ^
--sub-langs "hi,te" ^
--embed-subs ^
--write-thumbnail ^
--embed-thumbnail ^
--convert-thumbnails jpg ^
--add-metadata ^
-P OUTPUT_DIRECTORY ^
VIDEO_URL
```
**Dynamic Fields:**
- `height` (injects into `-f`)
- `format` (injects into `--merge-output-format`)
- `subtitle languages` (injects into `--sub-langs`)

## 🎵 Audio Download
```bash
yt-dlp ^
--cookies-from-browser chrome ^
--js-runtimes node ^
-f "251" ^
-x ^
--audio-format mp3 ^
--embed-thumbnail ^
--add-metadata ^
-P OUTPUT_DIRECTORY ^
VIDEO_URL
```
**Dynamic Fields:** Selected stream (251/140), audio codec (mp3/m4a), bitrate.

## 💬 Subtitle Only
```bash
yt-dlp ^
--cookies-from-browser chrome ^
--skip-download ^
--write-subs ^
--write-auto-subs ^
--sub-langs "hi,te,en" ^
--convert-subs srt ^
-P OUTPUT_DIRECTORY ^
VIDEO_URL
```
**Dynamic Fields:** Auto/Manual toggles, selected languages, output format (srt/vtt).

## 🖼 Thumbnail Only
```bash
yt-dlp ^
--skip-download ^
--write-thumbnail ^
--convert-thumbnails jpg ^
-P OUTPUT_DIRECTORY ^
VIDEO_URL
```
**Dynamic Fields:** `--convert-thumbnails` can be `jpg`, `png`, or `webp`.

## 📄 Transcript
```bash
yt-dlp ^
--skip-download ^
--write-auto-subs ^
--sub-langs "en" ^
--convert-subs vtt ^
-P OUTPUT_DIRECTORY ^
VIDEO_URL
```
**Note:** TranscriptEngine post-processes the VTT into TXT, SRT, or JSON.

## 📚 Playlist
```bash
yt-dlp ^
-f "bv*+ba/b" ^
--merge-output-format mp4 ^
-o "%(playlist_index)03d - %(title)s.%(ext)s"
```
**Dynamic Fields:** Output template (`-o`), concurrency, resume state.
