# Quality

## Goal

`switchflow_controller` aims for a practical Home Assistant Silver-style quality level.

That means:

- predictable setup, unload, and reload behavior
- explicit runtime logic
- strong automated coverage on maintenance-sensitive paths
- total Python test coverage of at least 95%
- conservative compatibility choices
- clear user-visible handling of configuration problems

## Required Validation

Core validation for the current `0.1` state:

```bash
/home/pacman/Projectes/switchflow_controller/.venv/bin/python -m compileall custom_components tests
/home/pacman/Projectes/switchflow_controller/.venv/bin/python -m pytest tests/unit/test_models.py tests/unit/test_storage_migrations.py tests/component/test_services.py tests/component/test_issues.py tests/component/test_config_flow.py tests/component/test_controller_runtime.py tests/component/test_alarm_notifications.py tests/component/test_illuminance_behavior.py tests/component/test_delayed_shutoff.py -q
```

The pytest configuration enforces `--cov-fail-under=95` for the integration package.

## Behavioral Quality Rules

1. Optional fields left unconfigured must not block the normal controller path.
2. Configured-but-unavailable entities must log warnings and surface a Repairs issue when a safe fallback exists.
3. `wait_time` is mandatory for every controller.
4. Controller IDs must remain stable and independent from display names.
5. Runtime listeners and timers must unload cleanly.

## Release Readiness

The repository should remain ready for:

- local pytest execution
- GitHub Actions test workflow
- HACS validation
- Hassfest validation

Relevant workflow files:

- [.github/workflows/tests_unit.yml](.github/workflows/tests_unit.yml)
- [.github/workflows/tests_component.yml](.github/workflows/tests_component.yml)
- [.github/workflows/validate_hacs.yml](.github/workflows/validate_hacs.yml)
- [.github/workflows/validate_hassfest.yml](.github/workflows/validate_hassfest.yml)