"""Config flow for the Switch Manager integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import selector
from homeassistant.util import slugify

from .const import (
    CONF_ACTIVATE_ON_DETECTION,
    CONF_ALARM_ENTITY,
    CONF_ALARM_NOTIFICATION_SCRIPT_ENTITY,
    CONF_ALARM_TIMER_ENTITY,
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
    TITLE,
)
from .models import ControllerConfig, GlobalConfig
from .storage import SwitchManagerStorage

STEP_GLOBAL_SETTINGS = "global_settings"
STEP_ADD_CONTROLLER = "add_controller"
STEP_SELECT_CONTROLLER = "select_controller"
STEP_CONTROLLER_ACTIONS = "controller_actions"
STEP_EDIT_CONTROLLER = "edit_controller"
STEP_DELETE_CONTROLLER = "delete_controller"


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
    """Create an optional selector field with a default only when present."""
    if default is None:
        return vol.Optional(key)
    return vol.Optional(key, default=default)


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
                CONF_TURN_OFF_WHEN_PRESENCE_CLEARS,
                default=values.turn_off_when_presence_clears if values else False,
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_WAIT_TIME,
                default=values.wait_time if values else 120,
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1,
                    mode=selector.NumberSelectorMode.BOX,
                    step=1,
                    unit_of_measurement="s",
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


class SwitchManagerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the initial setup flow for Switch Manager."""

    VERSION = 1

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
        self._selected_controller_id: str | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Show the main options menu."""
        storage = SwitchManagerStorage(self.hass)
        controllers = await storage.async_load()

        menu_options = [STEP_GLOBAL_SETTINGS, STEP_ADD_CONTROLLER]
        if controllers:
            menu_options.append(STEP_SELECT_CONTROLLER)

        return self.async_show_menu(step_id="init", menu_options=menu_options)

    async def async_step_global_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Edit the shared global configuration."""
        if user_input is not None:
            config = GlobalConfig.from_mapping(user_input)
            return self.async_create_entry(title="", data=config.as_dict())

        return self.async_show_form(
            step_id=STEP_GLOBAL_SETTINGS,
            data_schema=_build_global_config_schema(
                self._config_entry.options or self._config_entry.data
            ),
        )

    async def async_step_add_controller(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Create a new controller record."""
        if user_input is not None:
            storage = SwitchManagerStorage(self.hass)
            controllers = await storage.async_load()
            controller_name = _derive_controller_name(
                self.hass, user_input[CONF_MAIN_ENTITY]
            )
            controller = ControllerConfig.from_mapping(
                {
                    **user_input,
                    "name": controller_name,
                    "id": _build_controller_id(
                        controller_name,
                        {existing.controller_id for existing in controllers},
                    ),
                }
            )
            await storage.async_upsert(controller)
            await self.hass.config_entries.async_reload(self._config_entry.entry_id)
            return self.async_create_entry(title="", data=dict(self._config_entry.options))

        return self.async_show_form(
            step_id=STEP_ADD_CONTROLLER,
            data_schema=_build_controller_schema(),
        )

    async def async_step_select_controller(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Select a controller to edit or delete."""
        storage = SwitchManagerStorage(self.hass)
        controllers = await storage.async_load()

        if not controllers:
            return self.async_abort(reason="no_controllers")

        if user_input is not None:
            self._selected_controller_id = user_input["controller_id"]
            return await self.async_step_controller_actions()

        return self.async_show_form(
            step_id=STEP_SELECT_CONTROLLER,
            data_schema=_build_controller_select_schema(controllers),
        )

    async def async_step_controller_actions(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Show the action menu for the selected controller."""
        if self._selected_controller_id is None:
            return await self.async_step_select_controller()

        return self.async_show_menu(
            step_id=STEP_CONTROLLER_ACTIONS,
            menu_options=[STEP_EDIT_CONTROLLER, STEP_DELETE_CONTROLLER],
        )

    async def async_step_edit_controller(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Edit an existing controller."""
        storage = SwitchManagerStorage(self.hass)
        controllers = await storage.async_load()
        existing = next(
            (
                controller
                for controller in controllers
                if controller.controller_id == self._selected_controller_id
            ),
            None,
        )

        if existing is None:
            return self.async_abort(reason="controller_not_found")

        if user_input is not None:
            controller_name = _derive_controller_name(
                self.hass,
                user_input[CONF_MAIN_ENTITY],
                fallback=existing.name,
            )
            controller = ControllerConfig.from_mapping(
                {
                    **user_input,
                    "name": controller_name,
                    "id": existing.controller_id,
                }
            )
            await storage.async_upsert(controller)
            await self.hass.config_entries.async_reload(self._config_entry.entry_id)
            return self.async_create_entry(title="", data=dict(self._config_entry.options))

        return self.async_show_form(
            step_id=STEP_EDIT_CONTROLLER,
            data_schema=_build_controller_schema(existing.as_dict()),
        )

    async def async_step_delete_controller(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Delete an existing controller after confirmation."""
        if self._selected_controller_id is None:
            return await self.async_step_select_controller()

        if user_input is not None:
            storage = SwitchManagerStorage(self.hass)
            await storage.async_delete(self._selected_controller_id)
            await self.hass.config_entries.async_reload(self._config_entry.entry_id)
            return self.async_create_entry(title="", data=dict(self._config_entry.options))

        return self.async_show_form(
            step_id=STEP_DELETE_CONTROLLER,
            data_schema=vol.Schema({}),
        )