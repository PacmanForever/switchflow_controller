# SwitchFlow Controller

[![HACS][hacsbadge]][hacs]
[![Version](https://img.shields.io/github/v/tag/PacmanForever/switchflow_controller?label=version)](https://github.com/PacmanForever/switchflow_controller/tags)
[![Tests](https://github.com/PacmanForever/switchflow_controller/actions/workflows/tests.yml/badge.svg)](https://github.com/PacmanForever/switchflow_controller/actions/workflows/tests.yml)
[![Validate HACS](https://github.com/PacmanForever/switchflow_controller/actions/workflows/validate_hacs.yml/badge.svg)](https://github.com/PacmanForever/switchflow_controller/actions/workflows/validate_hacs.yml)
[![Validate Hassfest](https://github.com/PacmanForever/switchflow_controller/actions/workflows/validate_hassfest.yml/badge.svg)](https://github.com/PacmanForever/switchflow_controller/actions/workflows/validate_hassfest.yml)
[![License](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
![Coverage](https://img.shields.io/badge/coverage-%E2%89%A595%25-blue)

![Home Assistant](https://img.shields.io/badge/home%20assistant-2024.1.0%2B-blue)

A community Home Assistant custom integration for managing reusable motion-driven light and switch controllers with shared global configuration and per-controller behavior.

> [!IMPORTANT]
> `switchflow_controller` is designed as a compatibility-first replacement for repeated blueprint instances.
>
> The integration favors simple runtime logic, standard Home Assistant configuration flows, and minimal architecture surprises over aggressive feature scope.

## Features

- Shared global configuration for house-wide helpers and alarm-related references
- Multiple independent controllers for lights or switches
- Motion/presence-based activation with optional night-mode behavior
- Optional illuminance threshold gating
- Delayed shutoff with motion-clear waiting
- Optional per-controller alarm notification behavior
- Global script-based alarm notification action
- Conservative Home Assistant integration design focused on long-term maintainability

## Languages

The integration UI is currently available in:

- English
- Spanish
- Catalan

## Installation

### Via HACS

1. Make sure [HACS](https://hacs.xyz/) is installed.
2. Open HACS.
3. Go to `Integrations`.
4. Open the top-right menu and choose `Custom repositories`.
5. Add `https://github.com/PacmanForever/switchflow_controller` as the custom repository URL.
6. Select the `Integration` category.
7. Install `SwitchFlow Controller`.
8. Restart Home Assistant.

The repository already includes [validate_hacs.yml](.github/workflows/validate_hacs.yml) and [validate_hassfest.yml](.github/workflows/validate_hassfest.yml) so release readiness can be checked in CI.

### Manual

1. Copy `custom_components/switchflow_controller` into your Home Assistant `custom_components` directory.
2. Restart Home Assistant.

## Configuration

### Global Configuration

The integration uses one main global configuration entry.

This global configuration is intended for shared references that should not be repeated on every controller.

Initial global fields:

- `smart_mode_entity`
- `night_mode_entity`
- `alarm_entity`
- `alarm_timer_entity`
- `alarm_notification_script_entity`

These values are configured through the integration setup or options flow.

### Controllers

Each controller represents one functional automation unit.

Typical examples:

- one bathroom light
- one hallway light with a separate night light
- one staircase light zone with two motion/presence detectors

Each controller can define:

- a main entity
- an optional night entity
- up to two motion/presence detectors
- an optional illuminance sensor
- an optional illuminance threshold entity
- a wait time before shutoff
- whether motion activation is enabled
- whether alarm notifications are enabled for that controller
- up to two additional entities to turn off when the main entity turns on

### Why There Is No Global Hub

`switchflow_controller` does not use a fake "global hub".

Shared values belong to the main config entry, not to a special system object that pretends to be a normal grouping item.

This keeps the configuration model simpler and reduces maintenance risk across future Home Assistant versions.

## Runtime Behavior

The integration follows a deterministic runtime order.

### Global Smart Mode Gate

If `smart_mode_entity` is configured and is not `on`, controller automation behavior does not run.

### Motion Handling Priority

When motion is detected, the controller evaluates behavior in this order:

1. alarm notification path
2. night mode path
3. illuminance path
4. default activation path

### Night Mode

If the global night mode entity is active, the controller prefers the configured night entity when appropriate.

If no night entity is configured, the controller falls back to the main entity.

If the night entity is manually turned on, the controller still keeps the normal timer semantics so the automation does not lose track of shutoff behavior.

### Illuminance

If an illuminance sensor is configured, activation can be gated by an illuminance threshold.

If no threshold entity is configured, the integration may use a simple built-in default threshold.

### Delayed Shutoff

After activation, the controller waits for the configured delay and then waits until motion sensors are clear before turning entities off.

The shutoff model is intentionally restart-like so stale pending timers are cancelled when new triggers arrive.

If `turn_off_when_presence_clears` is enabled, the controller may turn off early as soon as all configured detectors are clear, regardless of whether they are motion or presence sensors.

## Alarm Notifications

Alarm notifications are split into two parts:

- the decision to notify is per controller through `notify_with_alarm`
- the action used to notify is global through `alarm_notification_script_entity`

The notification action must be configured as a `script` entity, not as a free-form service string.

If no notification script is configured, the controller skips notification safely.

The script is called through the `script` domain and currently receives these fields:

- `message`
- `controller_name`
- `trigger_entity_id`

Example script:

```yaml
alias: Send Alarm Message
sequence:
  - data:
      topic: alarm
      payload: "{{ message }}"
    action: mqtt.publish
mode: single
max_exceeded: silent
```

## Example Use Cases

### Bathroom Controller

- `main_entity`: bathroom light
- `detector_sensor_1`: bathroom motion sensor
- `wait_time`: 2 minutes
- `activate_on_detection`: enabled
- `notify_with_alarm`: disabled

### Hallway Controller With Night Light

- `main_entity`: hallway main light
- `night_entity`: hallway night light
- `detector_sensor_1`: hallway motion sensor
- `illuminance_sensor`: hallway lux sensor
- `wait_time`: 2 minutes
- `notify_with_alarm`: enabled

### Staircase Controller With Two Motion Sensors

- `main_entity`: staircase light
- `detector_sensor_1`: downstairs staircase motion sensor
- `detector_sensor_2`: upstairs staircase motion sensor
- `wait_time`: 3 minutes
- `notify_with_alarm`: enabled

## Manual Migration From Blueprint

Version 1 does not automatically import blueprint instances.

Migration from the old blueprint is manual.

The recommended approach is:

1. create the global configuration first
2. create one controller per functional light or zone
3. map each blueprint input to either a global field or a controller field
4. validate runtime behavior one controller at a time

A future version may provide migration helpers, but that is intentionally out of scope for the first stable release.

## Services

The current service surface is intentionally small.

Available services:

- `switchflow_controller.enable_controller`
- `switchflow_controller.disable_controller`
- `switchflow_controller.reset_controller_timer`
- `switchflow_controller.force_turn_on`
- `switchflow_controller.force_turn_off`

Services are expected to target controllers by stable internal ID.

See [custom_components/switchflow_controller/services.yaml](custom_components/switchflow_controller/services.yaml) for the field definitions.

## Error Visibility

Optional fields left unconfigured are valid and use fallback behavior.

If an entity was configured but is currently unavailable, `switchflow_controller` logs a warning and creates a transient warning in Home Assistant Repairs so the problem is visible without stopping the controller when a safe fallback exists.

## Quality Target

This integration is intended to follow a practical Home Assistant Silver-style quality standard.

That means the project should aim for:

- strong automated test coverage
- robust edge-case handling
- clean config flow behavior
- predictable reload and unload behavior
- compatibility with Hassfest and HACS validation

## Limitations

- Version 1 does not require hubs.
- Version 1 does not import blueprint YAML automatically.
- Version 1 intentionally avoids advanced inheritance or preset systems.
- Rich diagnostics and extra entities may be added later only if they provide clear operational value.

## Versioning

The manifest version should match the released repository tag.

Release notes for the current implementation live in [CHANGELOG.md](CHANGELOG.md).

## Tests

The project should include:

- component tests for configuration and runtime behavior
- unit tests for storage and migration logic
- coverage for edge cases such as missing entities, disabled controllers, unavailable states, and retriggered timers

## Development Notes

The integration should be built with conservative Home Assistant APIs and straightforward runtime logic.

If architecture decisions change during implementation, update `PLAN.md` first and then update the code.

For release preparation, run the local test slice first and then rely on the GitHub workflows in [.github/workflows/tests.yml](.github/workflows/tests.yml), [.github/workflows/validate_hacs.yml](.github/workflows/validate_hacs.yml), and [.github/workflows/validate_hassfest.yml](.github/workflows/validate_hassfest.yml).

Contributor-facing repository guidance is available in [CONTRIBUTING.md](CONTRIBUTING.md), [QUALITY.md](QUALITY.md), and [tests/README.md](tests/README.md).

[hacs]: https://hacs.xyz/
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg
