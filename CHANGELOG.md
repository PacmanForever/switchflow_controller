# Changelog

## 0.1.1

- Allowed `smart mode` and `night mode` global helpers to use either `binary_sensor` or `input_boolean` entities.
- Refined controller and global settings UI wording and ordering.
- Removed the unused controller `Area` field from the visible options flow.
- Reorganized GitHub Actions into separate unit, component, daily compatibility, HACS validation, and HA validation workflows.
- Raised automated test coverage to exceed the enforced `95%` minimum.

## 0.1.0

- Added the initial Home Assistant custom integration scaffold for `switch_manager`.
- Added config entry setup, global configuration flow, and storage-backed controller management.
- Added runtime controller handling for main entity activation, night-mode fallback, alarm notifications, illuminance gating, and delayed shutoff.
- Added warning-level Repairs issues for configured-but-unavailable entities.
- Added the initial manual service surface: enable, disable, reset timer, force on, and force off.
- Added unit and component tests for models, services, issues, config flow, controller runtime, alarm path, illuminance gating, and delayed shutoff behavior.
- Added GitHub Actions scaffolding for tests, HACS validation, and Hassfest validation.