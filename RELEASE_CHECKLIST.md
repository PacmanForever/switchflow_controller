# Release Checklist

## Repository Identity

Release-facing GitHub metadata has been updated for `PacmanForever/switchflow_controller`.

Before publishing broadly, do one last pass to confirm no placeholder values remain in non-release-facing internal docs.

## Release Metadata

1. Confirm the manifest version in [custom_components/switchflow_controller/manifest.json](custom_components/switchflow_controller/manifest.json) matches the release tag.
2. Update [CHANGELOG.md](CHANGELOG.md) with release-facing notes.
3. Verify [hacs.json](hacs.json) still matches the minimum supported Home Assistant version.
4. Publish a full GitHub release after tagging. A tag alone is not enough for HACS default-repository checks.

## Validation

Run locally:

```bash
/home/pacman/Projectes/switchflow_controller/.venv/bin/python -m compileall custom_components tests
/home/pacman/Projectes/switchflow_controller/.venv/bin/python -m pytest -q
```

Then confirm GitHub Actions passes:

- [.github/workflows/tests_unit.yml](.github/workflows/tests_unit.yml)
- [.github/workflows/tests_component.yml](.github/workflows/tests_component.yml)
- [.github/workflows/validate_hacs.yml](.github/workflows/validate_hacs.yml)
- [.github/workflows/validate_hassfest.yml](.github/workflows/validate_hassfest.yml)

## Publication Readiness

1. Ensure [LICENSE](LICENSE), [README.md](README.md), [CONTRIBUTING.md](CONTRIBUTING.md), and [QUALITY.md](QUALITY.md) are up to date.
2. Confirm [custom_components/switchflow_controller/services.yaml](custom_components/switchflow_controller/services.yaml) reflects the actual service surface.
3. Confirm [PLAN.md](PLAN.md) still matches the implemented architecture and deferred scope.
4. Decide whether to keep or remove development-only folders from version control expectations, such as `.vscode`.

## Final Manual Checks

1. Review Repairs strings and user-facing wording in [custom_components/switchflow_controller/strings.json](custom_components/switchflow_controller/strings.json).
2. Verify placeholders are gone from release-facing files.
3. Tag the release only after the manifest and changelog are aligned.

## HACS Default Repository Submission

1. Publish the GitHub release after tagging the matching version.
2. Confirm the repository is public and the latest release is visible on GitHub.
3. Confirm the repository has suitable GitHub topics for Home Assistant and HACS discovery.
4. Open a pull request against `hacs/default` adding `PacmanForever/switchflow_controller` under the `integration` category.
5. Merge only after the HACS maintainers accept the submission.
6. Use [docs/HACS_DEFAULT_SUBMISSION.md](docs/HACS_DEFAULT_SUBMISSION.md) as the handoff checklist for that PR.