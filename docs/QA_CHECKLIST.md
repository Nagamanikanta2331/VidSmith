# QA & Regression Testing Checklist

Before any major release (RC phase or Production), the following manual QA steps must be taken to guarantee Windows Explorer compatibility and artifact correctness.

## 1. Generate the Regression Dataset

Run the dataset generator script. This will use your local FFmpeg installation to deterministically construct a series of 1-second synthetic media files covering all permutations of supported formats and embedding strategies.

```bash
python scripts/generate_regression_dataset.py
```

Observe the CLI validation report to ensure no `ffmpeg` synthesis errors occurred.

## 2. Visual Inspection (Windows Explorer)

Navigate to the `regression/` output directory in Windows Explorer.

Ensure you change the View mode to **Large icons** or **Extra large icons**.

### Positive Cases Verification

*   **`valid_h264.mp4`**: 
    *   Thumbnail: Custom embedded thumbnail should display instead of a generic video frame.
    *   Details Pane: Right click -> Properties -> Details. Ensure Title, Artist, Album, and Year are populated.
*   **`valid_vp9.mp4` & `valid_av1.mp4`**: 
    *   Same expectations as H.264. (Note: Relies on Microsoft Store AV1/VP9 codecs being installed).
*   **`mp3_artwork.mp3`, `m4a_artwork.m4a`, `flac_artwork.flac`**:
    *   Thumbnail: Custom embedded artwork should display natively on the icon.
    *   Details Pane: Title, Artist, Album, and Year populated.

### Negative Cases Verification

*   **`no_metadata.mp4`, `no_thumbnail.mp4`, `no_chapters.mp4`**:
    *   Ensure they lack the respective features, but Explorer still successfully reads the file as valid media.
*   **`mp3_no_artwork.mp3`**:
    *   Should show the generic music file icon.

## 3. Playback Sanity Checks

Open the `valid_h264.mp4` file in the native **Movies & TV** app or **Windows Media Player**. Verify:
1. The video plays without corruption.
2. The custom thumbnail is briefly visible before playback begins, or in the gallery view.

Open the file in **VLC**. Verify:
1. Chapters (if generated) appear in the Playback -> Chapters menu.
2. Embedded subtitles (if generated) appear in the Subtitles -> Subtitle Track menu.
