# Contributing

## Scope

Contributions should preserve the current project direction:

- compatibility-first Home Assistant integration design
- explicit runtime behavior over abstract frameworks
- small, well-tested changes
- English-only code, docs, comments, and identifiers

## Before Opening a Pull Request

1. Read [README.md](README.md) for user-facing behavior and [QUALITY.md](QUALITY.md) for project quality requirements.
2. Check whether the change is already covered by an existing test.
3. Keep the change focused. Avoid bundling unrelated refactors.

## Development Expectations

1. Use the existing virtual environment or create an equivalent isolated Python environment.
2. Install test dependencies from [requirements-test.txt](requirements-test.txt).
3. Keep runtime behavior explicit and conservative.
4. Prefer standard Home Assistant APIs and stable patterns.
5. Do not introduce frontend-heavy features or decorative entities without a clear operational reason.

## Tests

Run the current local validation slice before submitting changes:

```bash
/home/pacman/Projectes/switchflow_controller/.venv/bin/python -m pytest tests/unit/test_models.py tests/unit/test_storage_migrations.py tests/component/test_services.py tests/component/test_issues.py tests/component/test_config_flow.py tests/component/test_controller_runtime.py tests/component/test_alarm_notifications.py tests/component/test_illuminance_behavior.py tests/component/test_delayed_shutoff.py -q
```

Also check the project compiles cleanly:

```bash
/home/pacman/Projectes/switchflow_controller/.venv/bin/python -m compileall custom_components tests
```

## Coding Rules

1. Keep optional configuration behavior non-blocking when not configured.
2. Treat configured-but-unavailable entities as visible configuration problems.
3. Add or update tests when behavior changes.
4. Update [README.md](README.md) when user-facing behavior changes.
5. Update [CHANGELOG.md](CHANGELOG.md) when preparing a release-facing change.

## Pull Request Notes

Include:

- a concise summary of the behavior change
- any runtime or config-flow impact
- the tests you ran
- any documentation updated as part of the change

## Repository Placeholders

The release-facing repository URLs now target the configured GitHub repository.

Before publishing broadly, do one final check that no placeholder values remain in badges, manifest metadata, or external links.