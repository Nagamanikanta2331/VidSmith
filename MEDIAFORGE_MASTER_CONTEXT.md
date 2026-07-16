# VidSmith Master Context

## CURRENT PRIORITIES
- **P0:** Fix `<=` TypeError in format filtering.
- **P0:** Fix Subtitle validator mapping mismatch.
- **P0:** Fix Thumbnail validator mapping mismatch.
- **P1:** Transcript extraction failure ("Unavailable").
- **P2:** Subtitle architecture redesign.
- **P3:** Download History database.
- **P4:** Plugin architecture.

## NEVER GUESS
Never guess.
If unsure:
1. Inspect the code.
2. Run the program.
3. Verify with `ffprobe`.
4. Then implement.

## DO NOT TOUCH
Do not modify these core systems unless strictly required for a bug fix:
- Wizard Engine
- DownloadJob
- Settings Store
- Cleanup
- Validator Framework

## ARCHITECTURE PRINCIPLES
Single Source of Truth flow. Never violate:
`DownloadJob` → `Provider` → `yt-dlp` → `Validator` → `Cleanup`

## 1. Repository State
- **Current Branch:** `main`
- **Current Tag:** `v1.0-phase-b-complete`
- **Python Version:** 3.10+
- **yt-dlp / FFmpeg / Ruff:** Latest stable
- **Pytest Status:** 65/65 passing
- **Target Platform:** Windows

## 2. Coding Rules
- **Never rewrite working architecture.** Build upon it.
- **Never bypass `DownloadJob`.** It is the single source of truth for arguments.
- **Never bypass validators.** `ffprobe` verification is mandatory.
- **Never duplicate yt-dlp logic.** Use the established provider options.
- **Always prefer yt-dlp over FFmpeg.** Let yt-dlp handle extraction/merging where possible.
- **Every change must pass Ruff and Pytest.** Maintain the 65/65 baseline.
- **Never fix more than one bug in a single commit.** Keep history atomic.

## 3. Developer Workflow
```text
Analyze
   ↓
Locate root cause
   ↓
Explain
   ↓
Minimal fix
   ↓
Ruff (Linting)
   ↓
Pytest (Unit Tests)
   ↓
Manual verification
   ↓
ffprobe (Validation)
   ↓
Commit
```
