# HACS Default Submission

This note is the final handoff for submitting `PacmanForever/switchflow_controller` to the default HACS catalog.

## What Is Already Ready In This Repository

- `custom_components/switchflow_controller/manifest.json` exists and includes `config_flow`, `version`, and release-facing URLs.
- `hacs.json` exists at the repository root.
- Local brand assets are present in `custom_components/switchflow_controller/brand/`.
- GitHub Actions workflows exist for unit tests, component tests, HACS validation, and Hassfest validation.
- The latest manifest version matches the latest tag: `0.4.8` / `v0.4.8`.

## What You Must Still Do On GitHub

1. Publish a GitHub release for `v0.4.8`.
2. Confirm the repository is public.
3. Confirm Issues are enabled.
4. Confirm the repository has a short description.
5. Confirm the repository has topics set.
6. Fork `hacs/default`.
7. Create a branch from `master` in your fork.
8. Add this repository to the `integration` file in alphabetical order.
9. Open the PR from your personal account as the repository owner or a major contributor.

## Exact Entry To Add

Add this line to the JSON array in `hacs/default/integration`:

```json
"PacmanForever/switchflow_controller",
```

## Suggested Pull Request Title

```text
Adds new integration [PacmanForever/switchflow_controller]
```

## Suggested Pull Request Checklist Text

Use the official `hacs/default` pull request template, then make sure these statements are true before submitting:

- I am the repository owner or a major contributor.
- The repository is public and hosted on GitHub.
- The repository is already valid as a HACS custom repository.
- HACS validation passes.
- Hassfest passes.
- A GitHub release exists for the current version.
- The repository is not archived.
- The repository has a description, topics, README, and Issues enabled.
- The entry was added to the correct file and kept in alphabetical order.

## Manual Checks For This Repository

- GitHub release exists for `v0.4.8`, not only the tag.
- Repository description is set.
- Repository topics include Home Assistant and HACS discoverability terms.
- The latest workflow runs on `main` are green.

## Notes

- HACS review can take a long time, often months.
- After the PR is merged, the repository appears after the next scheduled HACS scan.
- If the integration is specific to a country, add the `country` key to the released `hacs.json` first. This repository does not currently declare country restrictions.