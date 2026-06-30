"""Config flow for the SwitchFlow Controller integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.util import slugify

from .const import (
    CONF_ACTIVATE_ON_DETECTION,
    CONF_ALARM_ENTITY,
    CONF_ALARM_NOTIFICATION_SCRIPT_ENTITY,
    CONF_ALARM_TIMER_ENTITY,
    CONF_CONTROLLER_ID,
    CONF_DETECTOR_SENSOR_1,
    CONF_DETECTOR_SENSOR_2,
    CONF_ENABLED,
    CONF_ILLUMINANCE_SENSOR,
    CONF_ILLUMINANCE_THRESHOLD_ENTITY,
    CONF_MAIN_ENTITY,
    CONF_NIGHT_ENTITY,
    CONF_NIGHT_MODE_ENTITY,
    CONF_NOTIFY_WITH_ALARM,
    CONF_SMART_MODE_ENTITY,
    CONF_TURN_OFF_ENTITY_1,
    CONF_TURN_OFF_ENTITY_2,
    CONF_TURN_OFF_WHEN_PRESENCE_CLEARS,
    CONF_WAIT_TIME,
    DOMAIN,
    SUBENTRY_TYPE_CONTROLLER,
    TITLE,
)
from .models import ControllerConfig, GlobalConfig

STEP_GLOBAL_SETTINGS = "global_settings"
OPTIONS_GLOBALS_SAVED = "_globals_saved"

OPTIONAL_CONTROLLER_ENTITY_FIELDS = (
    CONF_NIGHT_ENTITY,
    CONF_DETECTOR_SENSOR_1,
    CONF_DETECTOR_SENSOR_2,
    CONF_ILLUMINANCE_THRESHOLD_ENTITY,
    CONF_ILLUMINANCE_SENSOR,
    CONF_TURN_OFF_ENTITY_1,
    CONF_TURN_OFF_ENTITY_2,
)
OWNED_CONTROLLER_ENTITY_FIELDS = (
    CONF_MAIN_ENTITY,
    CONF_NIGHT_ENTITY,
)


def _wait_time_selector_default(seconds: int) -> dict[str, int]:
    """Convert stored seconds into the duration selector shape."""
    hours, remainder = divmod(seconds, 3600)
    minutes, remaining_seconds = divmod(remainder, 60)
    return {
        "hours": hours,
        "minutes": minutes,
        "seconds": remaining_seconds,
    }


def _normalize_optional_entity_selector(value: Any) -> str | None:
    """Normalize optional entity selector values coming from forms."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise vol.Invalid(f"Expected entity id string, got {type(value)!r}")
    cleaned = value.strip()
    return cleaned or None


def _normalize_controller_input(user_input: dict[str, Any]) -> dict[str, Any]:
    """Convert controller form payloads into storage-friendly values."""
    wait_time_value = user_input[CONF_WAIT_TIME]
    if isinstance(wait_time_value, dict):
        wait_time_seconds = (
            int(wait_time_value.get("days", 0)) * 86400
            + int(wait_time_value.get("hours", 0)) * 3600
            + int(wait_time_value.get("minutes", 0)) * 60
            + int(wait_time_value.get("seconds", 0))
            + int(wait_time_value.get("milliseconds", 0)) // 1000
        )
    else:
        wait_time_seconds = int(wait_time_value)

    normalized_optional_entities = {
        field: _normalize_optional_entity_selector(user_input.get(field))
        for field in OPTIONAL_CONTROLLER_ENTITY_FIELDS
    }

    return {
        **user_input,
        **{
            field: value
            for field, value in normalized_optional_entities.items()
            if value is not None
        },
        CONF_WAIT_TIME: wait_time_seconds,
    }


def _entry_global_defaults(config_entry: config_entries.ConfigEntry) -> dict[str, Any]:
    """Return the effective global settings source for forms and runtime.

    Config-entry `data` contains the original setup payload. Once the options flow
    has been saved at least once, options must win even when the user cleared all
    optional globals and the resulting mapping would otherwise be empty.
    """
    options = dict(config_entry.options)
    if options.get(OPTIONS_GLOBALS_SAVED):
        options.pop(OPTIONS_GLOBALS_SAVED, None)
        return options
    return dict(config_entry.data)


def _derive_controller_name(
    hass, main_entity: str, *, fallback: str | None = None
) -> str:
    """Build a controller display name from the main entity."""
    state = hass.states.get(main_entity)
    if state is not None:
        friendly_name = state.attributes.get("friendly_name")
        if isinstance(friendly_name, str) and friendly_name.strip():
            return friendly_name.strip()

    object_id = main_entity.partition(".")[2].strip()
    if object_id:
        return object_id.replace("_", " ").strip().title()

    if fallback and fallback.strip():
        return fallback.strip()

    return "Controller"


def _optional_selector_field(
    key: str,
    selector_value: selector.Selector,
    default: Any | None = None,
) -> Any:
    """Create an optional selector field with a suggested value when present."""
    if default is None:
        return vol.Optional(key)
    return vol.Optional(key, description={"suggested_value": default})


def _build_global_config_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Build the schema used by config and options flows."""
    values = GlobalConfig.from_mapping(defaults).as_dict()
    smart_mode_selector = selector.EntitySelector(
        selector.EntitySelectorConfig(
            domain=["binary_sensor", "input_boolean"],
            multiple=False,
        )
    )
    night_mode_selector = selector.EntitySelector(
        selector.EntitySelectorConfig(
            domain=["binary_sensor", "input_boolean"],
            multiple=False,
        )
    )
    alarm_selector = selector.EntitySelector(
        selector.EntitySelectorConfig(domain="alarm_control_panel", multiple=False)
    )
    alarm_timer_selector = selector.EntitySelector(
        selector.EntitySelectorConfig(domain="timer", multiple=False)
    )

    return vol.Schema(
        {
            _optional_selector_field(
                CONF_SMART_MODE_ENTITY,
                smart_mode_selector,
                values.get(CONF_SMART_MODE_ENTITY),
            ): smart_mode_selector,
            _optional_selector_field(
                CONF_NIGHT_MODE_ENTITY,
                night_mode_selector,
                values.get(CONF_NIGHT_MODE_ENTITY),
            ): night_mode_selector,
            _optional_selector_field(
                CONF_ALARM_ENTITY,
                alarm_selector,
                values.get(CONF_ALARM_ENTITY),
            ): alarm_selector,
            _optional_selector_field(
                CONF_ALARM_TIMER_ENTITY,
                alarm_timer_selector,
                values.get(CONF_ALARM_TIMER_ENTITY),
            ): alarm_timer_selector,
            _optional_selector_field(
                CONF_ALARM_NOTIFICATION_SCRIPT_ENTITY,
                selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="script", multiple=False)
                ),
                values.get(CONF_ALARM_NOTIFICATION_SCRIPT_ENTITY),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="script", multiple=False)
            ),
        }
    )


def _build_controller_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Build the schema for creating or editing a controller."""
    values = ControllerConfig.from_mapping(defaults) if defaults else None

    main_entity_selector = selector.EntitySelector(
        selector.EntitySelectorConfig(domain=["light", "switch"], multiple=False)
    )
    detector_selector = selector.EntitySelector(
        selector.EntitySelectorConfig(domain="binary_sensor", multiple=False)
    )
    sensor_selector = selector.EntitySelector(
        selector.EntitySelectorConfig(domain="sensor", multiple=False)
    )
    illuminance_threshold_selector = selector.EntitySelector(
        selector.EntitySelectorConfig(domain="input_number", multiple=False)
    )

    return vol.Schema(
        {
            vol.Required(
                CONF_ENABLED,
                default=values.enabled if values else True,
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_MAIN_ENTITY,
                default=values.main_entity if values else vol.UNDEFINED,
            ): main_entity_selector,
            _optional_selector_field(
                CONF_NIGHT_ENTITY,
                main_entity_selector,
                values.night_entity if values else None,
            ): main_entity_selector,
            vol.Required(
                CONF_ACTIVATE_ON_DETECTION,
                default=values.activate_on_detection if values else True,
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_TURN_OFF_WHEN_PRESENCE_CLEARS,
                default=values.turn_off_when_presence_clears if values else False,
            ): selector.BooleanSelector(),
            _optional_selector_field(
                CONF_DETECTOR_SENSOR_1,
                detector_selector,
                values.detector_sensor_1 if values else None,
            ): detector_selector,
            _optional_selector_field(
                CONF_DETECTOR_SENSOR_2,
                detector_selector,
                values.detector_sensor_2 if values else None,
            ): detector_selector,
            _optional_selector_field(
                CONF_ILLUMINANCE_THRESHOLD_ENTITY,
                illuminance_threshold_selector,
                values.illuminance_threshold_entity if values else None,
            ): illuminance_threshold_selector,
            _optional_selector_field(
                CONF_ILLUMINANCE_SENSOR,
                sensor_selector,
                values.illuminance_sensor if values else None,
            ): sensor_selector,
            vol.Required(
                CONF_WAIT_TIME,
                default=_wait_time_selector_default(
                    values.wait_time if values else 120
                ),
            ): selector.DurationSelector(
                selector.DurationSelectorConfig(
                    enable_day=False,
                    allow_negative=False,
                )
            ),
            vol.Required(
                CONF_NOTIFY_WITH_ALARM,
                default=values.notify_with_alarm if values else False,
            ): selector.BooleanSelector(),
            _optional_selector_field(
                CONF_TURN_OFF_ENTITY_1,
                main_entity_selector,
                values.turn_off_entity_1 if values else None,
            ): main_entity_selector,
            _optional_selector_field(
                CONF_TURN_OFF_ENTITY_2,
                main_entity_selector,
                values.turn_off_entity_2 if values else None,
            ): main_entity_selector,
        }
    )


def _build_controller_select_schema(
    controllers: list[ControllerConfig],
) -> vol.Schema:
    """Build the schema used to select an existing controller."""
    options = [
        selector.SelectOptionDict(value=controller.controller_id, label=controller.name)
        for controller in controllers
    ]
    return vol.Schema(
        {
            vol.Required("controller_id"): selector.SelectSelector(
                selector.SelectSelectorConfig(options=options)
            )
        }
    )


def _build_controller_id(name: str, existing_ids: set[str]) -> str:
    """Generate a stable unique controller id from the display name."""
    base = slugify(name) or "controller"
    controller_id = base
    suffix = 2
    while controller_id in existing_ids:
        controller_id = f"{base}_{suffix}"
        suffix += 1
    return controller_id


def _main_entity_in_use(
    entry: config_entries.ConfigEntry,
    main_entity: str,
    *,
    ignore_subentry_id: str | None = None,
) -> bool:
    """Return whether another controller subentry already uses this main entity."""
    for subentry in entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_TYPE_CONTROLLER:
            continue
        if ignore_subentry_id is not None and subentry.subentry_id == ignore_subentry_id:
            continue
        if subentry.data.get(CONF_MAIN_ENTITY) == main_entity:
            return True
    return False


def _main_and_night_entities_match(controller_input: dict[str, Any]) -> bool:
    """Return whether main and night entities point to the same entity."""
    return controller_input.get(CONF_MAIN_ENTITY) == controller_input.get(CONF_NIGHT_ENTITY)


def _controlled_entity_in_use(
    entry: config_entries.ConfigEntry,
    controller_input: dict[str, Any],
    *,
    ignore_subentry_id: str | None = None,
) -> bool:
    """Return whether another controller already owns a main or night entity."""
    controlled_entities = {
        controller_input[field]
        for field in OWNED_CONTROLLER_ENTITY_FIELDS
        if controller_input.get(field) is not None
    }
    if not controlled_entities:
        return False

    for subentry in entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_TYPE_CONTROLLER:
            continue
        if ignore_subentry_id is not None and subentry.subentry_id == ignore_subentry_id:
            continue

        for field in OWNED_CONTROLLER_ENTITY_FIELDS:
            entity_id = subentry.data.get(field)
            if entity_id in controlled_entities:
                return True

    return False


def _controller_schema_defaults(
    submitted: dict[str, Any] | None,
    *,
    unique_id: str,
    title: str,
) -> dict[str, Any] | None:
    """Build schema defaults for controller forms from partial flow input."""
    if submitted is None:
        return None
    return {
        **submitted,
        CONF_CONTROLLER_ID: submitted.get(CONF_CONTROLLER_ID, unique_id),
        "name": submitted.get("name", title),
    }


class SwitchManagerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the initial setup flow for SwitchFlow Controller."""

    VERSION = 1

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: config_entries.ConfigEntry
    ) -> dict[str, type[config_entries.ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return {SUBENTRY_TYPE_CONTROLLER: SwitchManagerControllerSubentryFlow}

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> "SwitchManagerOptionsFlow":
        """Return the integration options flow."""
        return SwitchManagerOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the first setup step."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            config = GlobalConfig.from_mapping(user_input)
            return self.async_create_entry(title=TITLE, data=config.as_dict())

        return self.async_show_form(
            step_id="user",
            data_schema=_build_global_config_schema(),
        )


class SwitchManagerOptionsFlow(config_entries.OptionsFlow):
    """Handle runtime options for the integration."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize the options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Open global settings directly from options."""
        return await self.async_step_global_settings(user_input)

    async def async_step_global_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Edit the shared global configuration."""
        if user_input is not None:
            config = GlobalConfig.from_mapping(user_input)
            return self.async_create_entry(
                title="",
                data={
                    OPTIONS_GLOBALS_SAVED: True,
                    **config.as_dict(),
                },
            )

        return self.async_show_form(
            step_id=STEP_GLOBAL_SETTINGS,
            data_schema=_build_global_config_schema(_entry_global_defaults(self._config_entry)),
        )


class SwitchManagerControllerSubentryFlow(config_entries.ConfigSubentryFlow):
    """Manage controller subentries shown on the integration page."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.SubentryFlowResult:
        """Create a controller subentry."""
        entry = self._get_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            normalized_input = _normalize_controller_input(user_input)
            if _main_and_night_entities_match(normalized_input):
                errors["base"] = "main_and_night_entity_must_differ"
            elif _main_entity_in_use(entry, normalized_input[CONF_MAIN_ENTITY]):
                errors["base"] = "main_entity_already_configured"
            elif _controlled_entity_in_use(entry, normalized_input):
                errors["base"] = "controlled_entity_already_configured"
            else:
                controller_name = _derive_controller_name(
                    self.hass,
                    normalized_input[CONF_MAIN_ENTITY],
                )
                existing_ids = {
                    subentry.unique_id
                    for subentry in entry.subentries.values()
                    if subentry.subentry_type == SUBENTRY_TYPE_CONTROLLER
                    and subentry.unique_id is not None
                }
                return self.async_create_entry(
                    title=controller_name,
                    data=normalized_input,
                    unique_id=_build_controller_id(controller_name, existing_ids),
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_build_controller_schema(
                _controller_schema_defaults(
                    user_input,
                    unique_id="new_controller",
                    title=_derive_controller_name(
                        self.hass,
                        (user_input or {}).get(CONF_MAIN_ENTITY, ""),
                    ),
                )
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.SubentryFlowResult:
        """Reconfigure an existing controller subentry."""
        entry = self._get_entry()
        subentry = self._get_reconfigure_subentry()
        errors: dict[str, str] = {}

        if user_input is not None:
            normalized_input = _normalize_controller_input(user_input)
            if _main_and_night_entities_match(normalized_input):
                errors["base"] = "main_and_night_entity_must_differ"
            elif _main_entity_in_use(
                entry,
                normalized_input[CONF_MAIN_ENTITY],
                ignore_subentry_id=subentry.subentry_id,
            ):
                errors["base"] = "main_entity_already_configured"
            elif _controlled_entity_in_use(
                entry,
                normalized_input,
                ignore_subentry_id=subentry.subentry_id,
            ):
                errors["base"] = "controlled_entity_already_configured"
            else:
                controller_name = _derive_controller_name(
                    self.hass,
                    normalized_input[CONF_MAIN_ENTITY],
                    fallback=subentry.title,
                )
                return self.async_update_and_abort(
                    entry,
                    subentry,
                    title=controller_name,
                    data=normalized_input,
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_build_controller_schema(
                _controller_schema_defaults(
                    user_input,
                    unique_id=subentry.unique_id or "controller",
                    title=subentry.title,
                )
                or {
                    **dict(subentry.data),
                    CONF_CONTROLLER_ID: subentry.unique_id,
                    "name": subentry.title,
                }
            ),
            errors=errors,
        )