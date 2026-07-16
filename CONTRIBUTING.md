# Contributing to MediaForge

Thanks for your interest in improving MediaForge! This guide covers everything
you need to make your first contribution.

## Code of Conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). By
participating, you agree to uphold it.

## Getting Started

1. Fork and clone the repository:
   ```bash
   git clone https://github.com/your-username/MediaForge.git
   cd MediaForge
   ```
2. Create a virtual environment and install with the dev extra:
   ```bash
   python -m venv .venv
   # Windows:  .venv\Scripts\activate
   # Unix:     source .venv/bin/activate
   pip install -e ".[dev]"
   ```
3. Install the pre-commit hooks:
   ```bash
   pre-commit install
   ```

## Development Workflow

- Create a branch: `git checkout -b feature/short-description`
- Make your change with a clear, focused scope.
- Keep the download engine stable — it is considered feature complete. Only
  change it to fix a demonstrable bug, and include a reproduction.
- Run the quality gate locally before pushing:
  ```bash
  ruff check .
  black --check .
  mypy src/mediaforge
  pytest
  ```
- Commit using [Conventional Commits](https://www.conventionalcommits.org/)
  where possible (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`).

## Pull Requests

- Fill out the pull request template.
- Reference any related issue (`Closes #123`).
- Add or update tests for behaviour changes.
- Update `CHANGELOG.md` under the `[Unreleased]` section.
- Ensure CI is green. Maintainers review PRs on a best-effort basis.

## Architecture Notes

MediaForge enforces strict layer separation (see the Architecture section of
the README). In short:

- `cli/*` knows about Rich, never about yt-dlp or FFmpeg.
- `providers/youtube.py` owns all yt-dlp interaction.
- `executor.py` is the only glue between UI and engine.

Respect these boundaries — they keep the project testable and extensible.

## Reporting Bugs & Requesting Features

Use the issue templates. For security issues, follow [SECURITY.md](SECURITY.md)
instead of opening a public issue.

## License

By contributing, you agree that your contributions are licensed under the
project's [MIT License](LICENSE).
