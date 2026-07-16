# Architecture Decision Records (ADRs)

## Design Philosophy
- **Reliability over feature count:** Don't add features that compromise stability.
- **Windows-first compatibility:** Optimize for Windows behavior, then ensure cross-platform support where practical.
- **Native yt-dlp first:** Prefer yt-dlp capabilities over custom FFmpeg processing.
- **User experience over implementation cleverness:** Choose behavior that's simpler and more predictable for users.
- **Deterministic behavior:** The same inputs should produce the same outputs whenever possible.

## ADR-001: Best Download Output Format
**Decision:** Best Download always outputs MP4.
**Why:**
- Windows Explorer supports MP4 thumbnails best.
- Maximum compatibility across players and devices.
- Avoids MKV as a default, which sometimes has metadata display issues natively on Windows.
**Alternatives Considered:** MKV, WebM
**Decision Date:** 2026-07-15

## ADR-002: Metadata & Post-Processing Engine
**Decision:** Use `yt-dlp` for embedding instead of running a separate FFmpeg pass.
**Why:**
`yt-dlp` already performs:
- Chapters embedding
- Metadata writing
- Thumbnail embedding
- Subtitle embedding

Running FFmpeg manually afterwards caused regressions and duplicate work.
**Rule:** Use FFmpeg ONLY when `yt-dlp` cannot handle the specific post-processing task natively.
**Decision Date:** 2026-07-15
