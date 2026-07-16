# Manual Test Cases (Regression Log)

## TC-001: Standard Video Download (Best)
- **URL:** `https://youtu.be/jNQXAC9IVRw` (Me at the zoo)
- **Expected:**
  - ✓ thumbnail
  - ✓ metadata
  - ✓ chapters
  - ✓ subtitles
  - ✓ cleanup
- **Status:** PASS

## TC-002: Audio Only Download
- **URL:** (Standard music track)
- **Expected:**
  - ✓ thumbnail
  - ✓ metadata
  - ✓ playback
  - ✓ cleanup
- **Status:** PASS

## TC-003: Complex Video (Transcript / 157 Subs)
- **URL:** (KGF Trailer)
- **Expected:**
  - ✓ 157 subtitles detected
  - ✓ Manual: 0
  - ✓ Auto: 157
  - ✗ Transcript extraction fails ("Unavailable")
- **Status:** FAIL (Bug tracked as BUG-004)
