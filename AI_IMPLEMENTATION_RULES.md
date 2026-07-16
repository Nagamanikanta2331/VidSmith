# AI Implementation Rules

This document outlines the **immutable engineering principles** for the MediaForge project. These rules must be strictly followed by any AI or developer modifying the codebase. They ensure that the project's architecture, reliability, and code quality remain intact as new features and bug fixes are introduced.

---

## 1. Golden Rule

Every download mode MUST generate a yt-dlp command that is functionally equivalent to the manually verified reference command.

- MediaForge must NEVER invent new yt-dlp behaviour.
- If a feature already exists in yt-dlp, use it instead of recreating it in Python.
- The Python provider is responsible only for dynamically constructing the command from the `DownloadJob`.

---

## 2. Single Source of Truth

The data flow for downloads is strictly linear:

```text
Wizard
  ↓
DownloadJob
  ↓
YouTubeProvider
  ↓
yt-dlp
```

- No other module may generate yt-dlp arguments.
- `yt-dlp` remains the single source of truth for the actual download execution.

---

## 3. Work Incrementally (Development Workflow)

Implement only ONE logical fix or feature at a time.

For every development session:
1. Read AI_ONBOARDING.md
2. Read AI_IMPLEMENTATION_RULES.md
3. Read implementation_plan.md
4. Read MEDIAFORGE_ARCHITECTURE.md
5. Read MEDIAFORGE_BUG_TRACKER.md
6. Read MEDIAFORGE_COMMAND_REFERENCE.md
7. Implement ONLY the current P0 task.
8. Do not continue to the next P0 task without approval.
9. After implementation:
   - Ruff
   - Pytest
   - Manual yt-dlp test
   - ffprobe verification
10. Show the exact code diff.
11. Wait for review.

---

## 4. Never Guess

If any behavior is ambiguous:
- **Stop.**
- Inspect the existing implementation.
- Inspect the manual yt-dlp command.
- Inspect `ffprobe` output.
- Inspect tests.
- Only then implement.

Never invent new behavior.

---

## 5. Preserve Existing Architecture

Do not introduce:
- duplicate download pipelines
- duplicate command builders
- duplicate cleanup logic
- duplicate validation logic
- duplicate embedding logic

Everything must continue flowing through the existing provider architecture.

---

## 6. Debugging Rules

When fixing a runtime bug:
- Find the root cause.
- Do not patch symptoms.
- Do not silence exceptions.
- Do not bypass validation.
- Fix the actual source.

---

## 7. Code Quality

- Prefer modifying existing functions.
- Avoid creating new helper functions unless necessary.
- Avoid creating duplicate utility modules.
- Reuse existing models.
- Reuse existing enums.
- Reuse existing settings.

---

## 8. Regression Policy

Every bug fix or feature must preserve:
- Thumbnail embedding
- Metadata
- Chapters
- Subtitle embedding
- Cleanup
- Validation
- Progress UI
- Playlist support

No feature may regress while fixing another. Fix exactly one bug at a time.

---

## 9. Definition of Done

A task is complete only if **ALL** of the following are true:

- [ ] Ruff passes
- [ ] All pytest tests pass
- [ ] Manual verification using real downloads (not just unit tests) is complete
- [ ] No regressions in any existing features (UI, metadata, embedding, cleanup)
- [ ] Embedded thumbnails verified with `ffprobe` and Windows Explorer
- [ ] Embedded subtitles verified with `ffprobe`

Do not mark a task complete until every item passes.
