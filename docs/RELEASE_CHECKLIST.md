# Release Readiness Checklist

Before tagging a Release Candidate (RC) or Final Production build, ensure the following steps are executed and verified.

- [ ] **Unit Tests**: Ensure `pytest tests/unit/` passes with 100% success.
- [ ] **Integration Tests**: Ensure validation integration tests pass, with strictly checked mocked FFprobe invocations.
- [ ] **E2E Tests**: Ensure `pytest tests/e2e/` passes, verifying cleanup logic properly preserves final media.
- [ ] **Regression Generation**: Run `scripts/generate_regression_dataset.py` and ensure the summary reports successful creation of all synthetic files.
- [ ] **Windows QA Completed**: Complete manual visual inspection following the `docs/QA_CHECKLIST.md` in Windows Explorer.
- [ ] **Linux/macOS Smoke Tests** (If applicable): Verify basic CLI invocation.
- [ ] **Documentation Updated**: Ensure README and any new feature docs are accurate.
- [ ] **Changelog Prepared**: Update `CHANGELOG.md` with new features and architectural changes.
- [ ] **Version Bumped**: Increment version in `pyproject.toml` (or equivalent config).
- [ ] **Build Verified**: Run a fresh test installation of the packaged build to ensure dependencies resolve correctly.
