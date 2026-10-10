# SwitchFlow Controller

[![HACS][hacsbadge]][hacs]
[![Version](https://img.shields.io/github/v/tag/PacmanForever/switchflow_controller?label=version)](https://github.com/PacmanForever/switchflow_controller/tags)
[![Unit Tests](https://github.com/PacmanForever/switchflow_controller/actions/workflows/tests_unit.yml/badge.svg)](https://github.com/PacmanForever/switchflow_controller/actions/workflows/tests_unit.yml)
[![Component Tests](https://github.com/PacmanForever/switchflow_controller/actions/workflows/tests_component.yml/badge.svg)](https://github.com/PacmanForever/switchflow_controller/actions/workflows/tests_component.yml)
[![Validate HACS](https://github.com/PacmanForever/switchflow_controller/actions/workflows/validate_hacs.yml/badge.svg)](https://github.com/PacmanForever/switchflow_controller/actions/workflows/validate_hacs.yml)
[![Validate Hassfest](https://github.com/PacmanForever/switchflow_controller/actions/workflows/validate_hassfest.yml/badge.svg)](https://github.com/PacmanForever/switchflow_controller/actions/workflows/validate_hassfest.yml)
[![License](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
![Coverage](https://img.shields.io/badge/coverage-%E2%89%A595%25-blue)

![Home Assistant](https://img.shields.io/badge/home%20assistant-2025.3.0%2B-blue)

A community Home Assistant custom integration for managing reusable motion-driven light and switch controllers with shared global configuration and per-controller behavior.

> [!IMPORTANT]
> `switchflow_controller` is designed as a compatibility-first replacement for repeated blueprint instances.
>
> The integration favors simple runtime logic, standard Home Assistant configuration flows, and minimal architecture surprises over aggressive feature scope.

## Features

- Shared global configuration for house-wide helpers and alarm-related references
- Multiple independent controllers for lights or switches
- Guided three-step controller setup for switches/lights, motion and presence, and windows and doors
- Motion/presence-based activation with optional night-mode behavior
- Optional numeric illuminance threshold gating in lux
- Delayed shutoff with motion-clear waiting, defaulting to one hour
- Optional per-controller alarm notification behavior
- Armed motion and window/door responses using a shared, fixed-duration light timer
- Global script-based alarm notification action and alarm-light duration
- Conservative Home Assistant integration design focused on long-term maintainability

## Languages

The integration UI is currently available in:

- English
- Spanish
- Catalan

## Installation

### Via HACS

Current state: the repository is ready to be installed through HACS as a custom repository.

After it is accepted into the HACS default repository list, the custom-repository step below is no longer needed.

1. Make sure [HACS](https://hacs.xyz/) is installed.
2. Open HACS.
3. Go to `Integrations`.
4. Open the top-right menu and choose `Custom repositories`.
5. Add `https://github.com/PacmanForever/switchflow_controller` as the custom repository URL.
6. Select the `Integration` category.
7. Install `SwitchFlow Controller`.
8. Restart Home Assistant.

The repository already includes CI validation for unit tests, component tests, HACS validation, and Hassfest validation.

### HACS Default Repository Submission

To appear in the default HACS catalog without manually adding this repository, complete these release steps:

1. Publish a GitHub release whose tag matches the manifest version.
2. Confirm the GitHub repository is public and has a clear description, topics, and release notes.
3. Ensure the HACS and Hassfest workflows are green on `main`.
4. Open a pull request against `hacs/default` adding this repository in the `integration` category.
5. Wait for the HACS maintainers to review and merge that submission.

This repository is structured for step 4 already, but the actual inclusion in the default catalog must be completed from GitHub.

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
- `opening_alarm_light_duration` (defaults to 1 minute)

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
- whether the controller name is derived from the night entity instead of the main entity
- up to two motion/presence detectors
- up to two window or door opening sensors
- an optional illuminance sensor
- an optional numeric illuminance threshold in lux
- a wait time before shutoff (defaults to 1 hour)
- whether motion activation and detector-clear shutdown are enabled
- whether alarm notifications are enabled for that controller
- up to two additional entities to turn off when the main entity turns on

The controller form is split into three steps:

1. **Switches and lights**: the main and optional night entity, controller-name source, and linked turn-off entities.
2. **Motion and presence**: detectors, activation and shutoff behavior, illuminance settings, alarm-notification preference, and delayed shutoff.
3. **Windows and doors**: the two optional opening sensors used by the armed-alarm response.

Controller names must be unique for the selected name source. This means a main or night entity can be reused by another controller unless both controllers use that same entity as their name source.

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

If an illuminance sensor and a numeric threshold are configured, activation is allowed only while the measured illuminance is at or below that threshold in lux.

Leaving the threshold empty does not apply illuminance gating. Existing stored threshold-entity values remain readable for compatibility with earlier releases.

### Delayed Shutoff

After activation, the controller waits for the configured delay and then waits until motion sensors are clear before turning entities off.

This normal `wait_time` behavior applies when the alarm is not ready. When the alarm is ready, an eligible motion or opening response uses the global alarm-light duration instead and does not wait for detectors to clear.

The shutoff model is intentionally restart-like so stale pending timers are cancelled when new triggers arrive.

If `turn_off_when_presence_clears` is enabled, the controller may turn off early as soon as all configured detectors are clear, regardless of whether they are motion or presence sensors.

### Windows and Doors

Opening sensors are evaluated only while Smart Mode is enabled and the alarm is ready. The opening event must be an `off` to `on` transition. This behavior does not depend on the controller's `notify_with_alarm` option.

An eligible opening turns on the main entity if needed and starts or restarts the controller's alarm-light timer. If motion already started a normal controller timer, the opening switches it to the global alarm-light duration. The default duration is 1 minute.

### Alarm Sensor Behavior

The alarm is ready when the selected `alarm_entity` is in one of these states: `armed_away`, `armed_home`, `armed_night`, `armed_vacation`, or `armed_custom_bypass`. If `alarm_timer_entity` is configured, it must be `idle`; an active delay timer suppresses the alarm response.

| Sensor event | Requirements | Notification | Light and timer behavior |
| --- | --- | --- | --- |
| Motion or presence becomes `on` | Smart Mode enabled, alarm ready, and an activation path controls a light | Depends on `notify_with_alarm`; notification is optional | Uses the global `opening_alarm_light_duration`, even when notifications are disabled. |
| Window or door changes from `off` to `on` | Smart Mode enabled and alarm ready | Calls the global notification action when selected and available, regardless of `notify_with_alarm` | Turns on the main entity if needed and uses the global `opening_alarm_light_duration`. |

Motion and opening events share one alarm-light timer per controller. Each new eligible event restarts that timer and supersedes the controller's normal `wait_time` for the lights it manages. When the configured duration expires, those lights are turned off even if a detector still reports motion or presence. The global duration setting is shared, but timers for different controllers are independent.

If the alarm is not ready, motion follows the configured normal activation and shutoff rules, including `wait_time`. An opening does not take ownership of a light that was already on without an active controller timer.

## Alarm Notifications

Alarm notifications are split into two parts:

- the decision to notify is per controller through `notify_with_alarm`
- the action used to notify is global through `alarm_notification_script_entity`

The notification action must be configured as a `script` entity, not as a free-form service string. The selected script must be available when the sensor event occurs.

If no notification script is configured, the controller skips notification safely.

The script is called through the `script` domain and currently receives these fields:

- `message`: `SwitchFlow Controller alarm: Motion or presence detected in <area>` or `SwitchFlow Controller alarm: Window or door opened in <area>`. The area is read from the configured main switch/light; if it has no Home Assistant area, the controller name is used instead.
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

### Armed Front Door Response

- `main_entity`: entrance light
- `opening_sensor_1`: front door contact
- `opening_sensor_2`: patio door contact
- `opening_alarm_light_duration`: 1 minute (global setting)
- `alarm_entity`: armed alarm panel (global setting)
- `alarm_notification_script_entity`: notification script (global setting)

While the alarm is ready, an opening or qualifying motion event uses the shared one-minute alarm-light timer for that controller. Each new event restarts the timer; expiry turns off the lights it manages even if a detector remains active. Notifications remain optional for motion.

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

Keep this README focused on user-facing behavior. Add specific regression tests for edge cases and timer interactions.

For release preparation, run the local test slice first and then rely on the GitHub workflows in [.github/workflows/tests_unit.yml](.github/workflows/tests_unit.yml), [.github/workflows/tests_component.yml](.github/workflows/tests_component.yml), [.github/workflows/validate_hacs.yml](.github/workflows/validate_hacs.yml), and [.github/workflows/validate_hassfest.yml](.github/workflows/validate_hassfest.yml).

Contributor-facing repository guidance is available in [CONTRIBUTING.md](CONTRIBUTING.md), [QUALITY.md](QUALITY.md), and [tests/README.md](tests/README.md).

[hacs]: https://hacs.xyz/
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg
