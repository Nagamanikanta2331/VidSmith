# Release Checklist

Run this checklist before cutting any new git tag.

- [ ] `ruff check .` (Linting passes)
- [ ] `pytest` (All tests pass)
- [ ] Manual test: Best Download
- [ ] Manual test: Custom Video
- [ ] Manual test: Audio
- [ ] Manual test: Subtitle
- [ ] Manual test: Transcript
- [ ] Manual test: Thumbnail
- [ ] Manual test: Playlist
- [ ] Output verification: `ffprobe` confirms streams and metadata.
- [ ] Output verification: Windows Explorer displays thumbnail.
- [ ] Update `CHANGELOG.md`
- [ ] Create Git Tag
