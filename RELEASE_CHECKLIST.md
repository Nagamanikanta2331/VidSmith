# Release Checklist

Status for the first public release target: `v1.0.0`.

## Environment

- [x] `mediaforge doctor --no-network` reports required tools: Python, yt-dlp, FFmpeg.
- [x] Optional tools verified or consciously waived: curl_cffi and mutagen installed;
      AtomicParsley and Deno reported as optional recommendations.

## Functionality

- [x] **Installation** - editable install and built wheel install both work.
- [x] **Downloads** - Best Download uses yt-dlp parity selector:
      `bv*+ba/b --merge-output-format mp4`.
- [x] **Resume** - yt-dlp resume remains enabled with `.part` files (`continuedl=True`).
- [x] **Audio** - audio mode retains existing yt-dlp post-processing path.
- [x] **Subtitles** - subtitle failures are captured per language and are non-fatal.
- [x] **Thumbnail** - summary reports MP4 support.
- [x] **Metadata** - metadata embedding remains enabled for recommended mode.
- [x] **Chapters** - chapter embedding remains enabled via FFmpeg metadata postprocessor.
- [x] **Progress UI** - existing percent, bytes, speed, ETA, and stage UI preserved.
- [x] **Doctor command** - `mediaforge doctor --no-network` exits cleanly.

## Packaging

- [x] `python -m build` succeeds: sdist and wheel created.
- [x] `python -m twine check dist\*` passes.
- [x] Wheel installs into a clean venv; installed `mediaforge --version` works.
- [x] Installed `mediaforge doctor --no-network` works from the clean venv.
- [x] `pyproject.toml` version matches `mediaforge.config.APP_VERSION` (`1.0.0`).

## Quality

- [x] `python -m ruff check .` passes.
- [x] `python -m black --check .` passes.
- [x] `python -m mypy src\mediaforge` passes.
- [x] `python -m pytest` passes.
- [x] Pre-commit configuration is present.

## Documentation

- [x] README rewritten for GitHub and PyPI.
- [x] CHANGELOG uses Keep a Changelog format.
- [x] Governance files present: LICENSE, CONTRIBUTING, SECURITY, CODE_OF_CONDUCT, SUPPORT.
- [x] Issue templates and pull request template are present.

## CI / Release

- [x] GitHub Actions CI covers lint, format, type check, tests, build, and package validation.
- [x] Release workflow builds artifacts, smoke-tests installs, publishes to PyPI, and creates a GitHub release.
- [x] Tag convention documented: `v1.0.0` must match package version `1.0.0`.
- [x] PyPI trusted-publishing step included in release workflow.
- [x] Post-release verification command documented: `pip install mediaforge`.
