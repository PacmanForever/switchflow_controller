# Changelog

## 0.3.3

- Added a full Spanish translation for the integration UI.
- Refined Catalan controller wording to use `controlador/controladors` consistently in the visible UI.

## 0.3.2

- Fixed detector-driven delayed shutoff so active presence or motion while a controlled entity is already on refreshes the timer instead of allowing an unexpected turn-off when `turn_off_when_presence_clears` is disabled.
- Added regression coverage for the detector timer refresh path and the `timedelta` wait-time normalizer branch.

## 0.3.1

- Stopped controller automation completely while `smart_mode_entity` is off, so manual light changes no longer restart timers or cause automatic shutoff until smart mode is enabled again.

## 0.3.0

- Renamed the Home Assistant integration domain and package from `switch_manager` to `switchflow_controller` so the repository name, manifest domain, services, and install path are aligned.
- Updated tests, scripts, coverage configuration, and release documentation to use `custom_components/switchflow_controller` consistently.
- Kept one-time compatibility for legacy controller storage by reading the old `switch_manager.controllers` storage key and saving it back under the new domain key.
- This release is a breaking change for existing Home Assistant installations because old `switch_manager.*` services and config entries do not automatically migrate to the new integration domain.

## 0.2.0

- Rebranded the integration to `SwitchFlow Controller` to avoid Home Assistant and HACS branding collisions with another `Switch Manager` integration.
- Marked the integration as a single config entry so Home Assistant no longer offers duplicate main-entry creation while controller subentries remain available.
- Added Catalan translations for the config flow and controller subentry flow so Home Assistant no longer shows raw translation keys in Catalan UI sessions.
- Updated repository metadata and documentation for the renamed `PacmanForever/switchflow_controller` repository.

## 0.1.9

- Serialized each controller timer lifecycle so concurrent restart/cancel paths cannot leave orphaned timer tasks behind.
- Reloaded only the controller runtimes affected by a controller-level configuration change instead of restarting all controllers together.
- Prevented controller ownership conflicts for main and night entities while still allowing explicit `turn_off_entity_1` and `turn_off_entity_2` cross-controller targets.

## 0.1.8

- Fixed the Home Assistant form defaults so clearing optional global and controller entity selectors no longer repopulates old values when the form is reopened.
- Preserved explicitly saved empty global settings instead of falling back to the original config-entry data.
- Rejected controller configurations where the main and night entities are the same.

## 0.1.7

- Fixed the outdated config-flow helper unit test so the release and CI suites match the new duration-based `wait_time` selector.

## 0.1.6

- Replaced the controller turn-off delay field with a Home Assistant duration selector shown as `hh:mm:ss` while keeping stored values compatible in seconds.
- Fixed controller reconfiguration so clearing optional entity selectors persists the removal instead of restoring old values on the next edit.
- Suppressed false unavailable warnings for optional night entities so fallback behavior stays silent instead of creating a Repairs issue.
- Added regression coverage for clearing optional global settings and controller optional entities through the config flows.

## 0.1.5

- Blocked creating or reconfiguring multiple controllers that use the same main switch/light.
- Fixed delayed shutoff so controllers without detectors still turn off after the configured delay and active detectors keep extending the timer until they clear.
- Resumed the shutdown timer when a controlled light is already on during runtime startup.
- Avoided false unavailable warnings caused by the startup-only timer probe before entities are fully loaded.

## 0.1.4

- Synchronized controller shutoff so turning off either the main or night entity also turns off the other one and cancels the timer.
- Refined controller form wording to better describe detector-clear behavior relative to the configured delay.
- Fixed the controller reconfigure success dialog so it shows a proper translated message instead of a raw translation key.

## 0.1.3

- Avoided false configured-entity unavailable warnings during Home Assistant startup by deferring eager validation until the core is fully running.
- Cleared stale configured-entity warnings for each controller when its runtime starts so old startup warnings do not linger after reloads.

## 0.1.2

- Migrated controllers from storage-backed records to Home Assistant config subentries so they appear directly under the integration page.
- Added one-time migration from legacy controller storage into subentries during setup.
- Simplified integration options to global settings only and moved controller add/edit flows into subentry creation and reconfiguration.
- Made manual main-entity activation restart the shutdown timer and made timer expiry extend itself while a detector remains active.
- Clarified the controller UI so detector-clear shutdown behavior is explicit relative to the configured delay.

## 0.1.1

- Allowed `smart mode` and `night mode` global helpers to use either `binary_sensor` or `input_boolean` entities.
- Refined controller and global settings UI wording and ordering.
- Removed the unused controller `Area` field from the visible options flow.
- Reorganized GitHub Actions into separate unit, component, daily compatibility, HACS validation, and HA validation workflows.
- Raised automated test coverage to exceed the enforced `95%` minimum.

## 0.1.0

- Added the initial Home Assistant custom integration scaffold for `switchflow_controller`.
- Added config entry setup, global configuration flow, and storage-backed controller management.
- Added runtime controller handling for main entity activation, night-mode fallback, alarm notifications, illuminance gating, and delayed shutoff.
- Added warning-level Repairs issues for configured-but-unavailable entities.
- Added the initial manual service surface: enable, disable, reset timer, force on, and force off.
- Added unit and component tests for models, services, issues, config flow, controller runtime, alarm path, illuminance gating, and delayed shutoff behavior.
- Added GitHub Actions scaffolding for tests, HACS validation, and Hassfest validation.