# MediaForge Architecture Reference

## 1. System Architecture Diagram

```text
User
 │
 ▼
Metadata Analyzer
 │
 ▼
Wizard
 │
 ▼
WizardState
 │
 ▼
DownloadJob
 │
 ▼
YouTubeProvider
 │
 ▼
yt-dlp Execution Engine
 │
 ▼
Validator (ffprobe)
 │
 ▼
Cleanup
 │
 ▼
Summary
```

## 2. Provider Internals Diagram

```text
ProviderFactory
 │
 ▼
BaseProvider
 │
 ├── YouTubeProvider (Specific extraction logic)
 │
 ├── ConfigResolution (Merge defaults & job config)
 │
 └── CommandBuilder (Map job fields to yt-dlp options)
```

## 3. DownloadJob Field Reference

`quality`
- **Values:** `best`, `2160`, `1440`, `1080`, `720`, `480`, `audio_only`
- **Maps to:** `_video_format_selector()`
- **Used by:** `YouTubeProvider`
- **Ignored by:** Audio mode, Subtitle-only mode

`format_spec`
- **Values:** String format (e.g. `bv*+ba/b`, `251`)
- **Maps to:** `-f` / `format` option
- **Used by:** CommandBuilder
- **Ignored by:** Subtitle-only, Thumbnail-only modes

`subtitle_langs`
- **Values:** Comma-separated strings (e.g. `en,hi,te`)
- **Maps to:** `--sub-langs`
- **Used by:** yt-dlp options dictionary
- **Ignored by:** Audio-only, Thumbnail-only modes

`thumbnail_mode`
- **Values:** `embed`, `save`, `none`
- **Maps to:** `--write-thumbnail`, `--embed-thumbnail`
- **Used by:** CommandBuilder
- **Ignored by:** Subtitle-only mode

## 4. Wizard → DownloadJob Mapping

| Wizard Step | State Key | DownloadJob Field | Description |
|---|---|---|---|
| Quality Selection | `quality` | `job.quality` | Target resolution or audio-only toggle. |
| Output Directory | `output_dir` | `job.output_dir` | Path resolved from settings/user input. |
| Subtitle Languages | `subtitle_langs` | `job.subtitle_langs` | Selected langs for download/embed. |
| Thumbnail | `thumbnail_mode` | `job.thumbnail_mode` | Keep thumbnail, embed it, or discard. |
| Audio Codec | `audio_codec` | `job.audio_codec` | Specific codec preference (mp3, aac, flac). |
| Format Choice | `video_format` | `job.merge_format` | Target container format (mp4, mkv). |

## 5. yt-dlp Option Map

This tracks how domain concepts map down to the underlying `YoutubeDL` options.

```text
writesubtitles
   ↓
job.subtitle_mode / job.subtitle_langs
   ↓
_base_download_options()
   ↓
YoutubeDL({ 'writesubtitles': True })

postprocessors (EmbedThumbnail)
   ↓
job.thumbnail_mode == 'embed'
   ↓
_base_download_options()
   ↓
YoutubeDL({ 'postprocessors': [{'key': 'EmbedThumbnail'}] })

format
   ↓
job.quality (or format_spec)
   ↓
_video_format_selector()
   ↓
YoutubeDL({ 'format': '...' })
```
