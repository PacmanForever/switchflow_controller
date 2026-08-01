"""Component tests for switchflow_controller config and options flows."""

from __future__ import annotations

from types import MappingProxyType
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
import voluptuous as vol

from homeassistant.config_entries import ConfigSubentry
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.switchflow_controller.config_flow import (
    OPTIONS_GLOBALS_SAVED,
    SwitchManagerConfigFlow,
    SwitchManagerControllerSubentryFlow,
    SwitchManagerOptionsFlow,
    _build_global_config_schema,
    _wait_time_selector_default,
)
from custom_components.switchflow_controller.const import (
    CONF_OPENING_ALARM_LIGHT_DURATION,
    DOMAIN,
    SUBENTRY_TYPE_CONTROLLER,
)


@pytest.mark.asyncio
async def test_user_flow_creates_single_instance_entry(hass) -> None:
    """The user flow should create one config entry and then block duplicates."""
    flow = SwitchManagerConfigFlow()
    flow.hass = hass

    with patch.object(flow, "_async_current_entries", return_value=[]):
        result = await flow.async_step_user({})

    assert result["type"] is FlowResultType.CREATE_ENTRY

    duplicate_flow = SwitchManagerConfigFlow()
    duplicate_flow.hass = hass
    with patch.object(duplicate_flow, "_async_current_entries", return_value=[object()]):
        duplicate = await duplicate_flow.async_step_user()

    assert duplicate["type"] is FlowResultType.ABORT
    assert duplicate["reason"] == "single_instance_allowed"


@pytest.mark.asyncio
async def test_options_flow_clears_optional_global_entities(hass) -> None:
    """Clearing optional global selectors should replace stored options with an empty payload."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="SwitchFlow Controller",
        data={},
        options={
            "smart_mode_entity": "input_boolean.smart_mode",
            "night_mode_entity": "input_boolean.night_mode",
            "alarm_entity": "alarm_control_panel.home",
            "alarm_timer_entity": "timer.home_alarm",
            "alarm_notification_script_entity": "script.notify_alarm",
        },
    )
    flow = SwitchManagerOptionsFlow(config_entry)
    flow.hass = hass

    result = await flow.async_step_global_settings({})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {OPTIONS_GLOBALS_SAVED: True}


def test_global_settings_schema_defaults_opening_alarm_light_duration() -> None:
    """Global settings should default the opening alarm light duration to one minute."""
    assert _build_global_config_schema({})({})[CONF_OPENING_ALARM_LIGHT_DURATION] == {
        "hours": 0,
        "minutes": 1,
        "seconds": 0,
    }


@pytest.mark.asyncio
async def test_controller_subentry_flow_adds_controller(hass) -> None:
    """The controller subentry flow should create a subentry result."""
    flow = SwitchManagerControllerSubentryFlow()
    flow.hass = hass
    flow.handler = ("entry-1", SUBENTRY_TYPE_CONTROLLER)
    flow.context = {"source": "user"}

    with patch.object(flow, "_get_entry", return_value=SimpleNamespace(subentries={})):
        result = await flow.async_step_user(
        {
            "main_entity": "light.hallway",
            "illuminance_threshold_lux": 25,
            "wait_time": 120,
            "enabled": True,
            "activate_on_detection": True,
            "turn_off_when_presence_clears": False,
            "notify_with_alarm": False,
        }
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["unique_id"] == "hallway"
    assert result["title"] == "Hallway"
    assert result["data"]["main_entity"] == "light.hallway"
    assert result["data"]["illuminance_threshold_lux"] == 25.0


@pytest.mark.asyncio
async def test_controller_subentry_flow_collects_windows_and_doors_in_third_step(hass) -> None:
    """The staged controller flow persists opening sensors only after its third step."""
    flow = SwitchManagerControllerSubentryFlow()
    flow.hass = hass
    flow.handler = ("entry-1", SUBENTRY_TYPE_CONTROLLER)
    flow.context = {"source": "user"}

    with patch.object(flow, "_get_entry", return_value=SimpleNamespace(subentries={})):
        motion_step = await flow.async_step_user(
            {
                "enabled": True,
                "main_entity": "light.hallway",
                "use_night_entity_name": False,
            }
        )
        windows_step = await flow.async_step_motion_presence(
            {
                "activate_on_detection": False,
                "turn_off_when_presence_clears": False,
                "notify_with_alarm": False,
                "wait_time": {"minutes": 1},
            }
        )
        result = await flow.async_step_windows_doors(
            {
                "opening_sensor_1": "binary_sensor.hallway_window",
                "opening_sensor_2": "binary_sensor.hallway_door",
            }
        )

    assert motion_step["type"] is FlowResultType.FORM
    assert motion_step["step_id"] == "motion_presence"
    assert windows_step["type"] is FlowResultType.FORM
    assert windows_step["step_id"] == "windows_doors"
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["opening_sensor_1"] == "binary_sensor.hallway_window"
    assert result["data"]["opening_sensor_2"] == "binary_sensor.hallway_door"


@pytest.mark.asyncio
async def test_controller_reconfigure_flow_collects_windows_and_doors_in_third_step(hass) -> None:
    """Reconfiguration keeps existing data until the windows and doors step submits."""
    flow = SwitchManagerControllerSubentryFlow()
    flow.hass = hass
    flow.handler = ("entry-1", SUBENTRY_TYPE_CONTROLLER)
    flow.context = {"source": "reconfigure", "subentry_id": "sub-1"}
    hass.config_entries.async_update_subentry = Mock(return_value=True)
    subentry = ConfigSubentry(
        data=MappingProxyType(
            {
                "main_entity": "light.hallway",
                "wait_time": 60,
                "enabled": True,
                "activate_on_detection": False,
                "turn_off_when_presence_clears": False,
                "notify_with_alarm": False,
            }
        ),
        subentry_id="sub-1",
        subentry_type=SUBENTRY_TYPE_CONTROLLER,
        title="Hallway",
        unique_id="hallway",
    )
    entry = SimpleNamespace(subentries={"sub-1": subentry})

    with patch.object(flow, "_get_entry", return_value=entry), patch.object(
        flow, "_get_reconfigure_subentry", return_value=subentry
    ):
        motion_step = await flow.async_step_reconfigure(
            {"enabled": True, "main_entity": "light.hallway", "use_night_entity_name": False}
        )
        windows_step = await flow.async_step_reconfigure_motion_presence(
            {
                "activate_on_detection": False,
                "turn_off_when_presence_clears": False,
                "notify_with_alarm": False,
                "wait_time": {"minutes": 1},
            }
        )
        result = await flow.async_step_reconfigure_windows_doors(
            {"opening_sensor_1": "binary_sensor.hallway_window"}
        )

    assert motion_step["step_id"] == "reconfigure_motion_presence"
    assert windows_step["step_id"] == "reconfigure_windows_doors"
    assert result["reason"] == "reconfigure_successful"
    assert hass.config_entries.async_update_subentry.call_args.kwargs["data"][
        "opening_sensor_1"
    ] == "binary_sensor.hallway_window"


@pytest.mark.asyncio
async def test_controller_subentry_flow_uses_night_entity_for_name_when_selected(hass) -> None:
    """A controller can derive its title and ID from its night entity."""
    flow = SwitchManagerControllerSubentryFlow()
    flow.hass = hass
    flow.handler = ("entry-1", SUBENTRY_TYPE_CONTROLLER)
    flow.context = {"source": "user"}
    hass.states.async_set("light.hallway_night", "off", {"friendly_name": "Hallway Night"})

    with patch.object(flow, "_get_entry", return_value=SimpleNamespace(subentries={})):
        result = await flow.async_step_user(
            {
                "main_entity": "light.hallway",
                "night_entity": "light.hallway_night",
                "use_night_entity_name": True,
                "wait_time": 120,
                "enabled": True,
                "activate_on_detection": False,
                "turn_off_when_presence_clears": False,
                "notify_with_alarm": False,
            }
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["unique_id"] == "hallway_night"
    assert result["title"] == "Hallway Night"
    assert result["data"]["use_night_entity_name"] is True


@pytest.mark.asyncio
async def test_controller_subentry_flow_reconfigures_existing_controller(hass) -> None:
    """The controller subentry reconfigure flow should update title and data."""
    flow = SwitchManagerControllerSubentryFlow()
    flow.hass = hass
    flow.handler = ("entry-1", SUBENTRY_TYPE_CONTROLLER)
    flow.context = {"source": "reconfigure", "subentry_id": "sub-1"}
    hass.config_entries.async_update_subentry = Mock(return_value=True)
    subentry = ConfigSubentry(
        data=MappingProxyType(
            {
                "main_entity": "light.hallway",
                "wait_time": 120,
                "enabled": True,
                "activate_on_detection": True,
                "turn_off_when_presence_clears": False,
                "notify_with_alarm": False,
            }
        ),
        subentry_id="sub-1",
        subentry_type=SUBENTRY_TYPE_CONTROLLER,
        title="Hallway",
        unique_id="hallway",
    )
    entry = SimpleNamespace(subentries={"sub-1": subentry})

    with patch.object(flow, "_get_entry", return_value=entry), patch.object(
        flow, "_get_reconfigure_subentry", return_value=subentry
    ):
        result = await flow.async_step_reconfigure(
        {
            "main_entity": "light.kitchen",
            "wait_time": 180,
            "enabled": True,
            "activate_on_detection": True,
            "turn_off_when_presence_clears": False,
            "notify_with_alarm": False,
        }
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    hass.config_entries.async_update_subentry.assert_called_once()
    assert hass.config_entries.async_update_subentry.call_args.kwargs["title"] == "Kitchen"
    assert hass.config_entries.async_update_subentry.call_args.kwargs["data"]["wait_time"] == 180


@pytest.mark.asyncio
async def test_controller_subentry_flow_clears_optional_entities_on_reconfigure(hass) -> None:
    """Cleared optional entity selectors should be persisted as empty values."""
    flow = SwitchManagerControllerSubentryFlow()
    flow.hass = hass
    flow.handler = ("entry-1", SUBENTRY_TYPE_CONTROLLER)
    flow.context = {"source": "reconfigure", "subentry_id": "sub-1"}
    hass.config_entries.async_update_subentry = Mock(return_value=True)
    subentry = ConfigSubentry(
        data=MappingProxyType(
            {
                "main_entity": "light.hallway",
                "wait_time": 120,
                "enabled": True,
                "activate_on_detection": True,
                "turn_off_when_presence_clears": False,
                "notify_with_alarm": False,
                "night_entity": "light.hallway_night",
                "detector_sensor_1": "binary_sensor.hallway_motion",
            }
        ),
        subentry_id="sub-1",
        subentry_type=SUBENTRY_TYPE_CONTROLLER,
        title="Hallway",
        unique_id="hallway",
    )
    entry = SimpleNamespace(subentries={"sub-1": subentry})

    with patch.object(flow, "_get_entry", return_value=entry), patch.object(
        flow, "_get_reconfigure_subentry", return_value=subentry
    ):
        result = await flow.async_step_reconfigure(
            {
                "main_entity": "light.hallway",
                "wait_time": 120,
                "enabled": True,
                "activate_on_detection": True,
                "turn_off_when_presence_clears": False,
                "notify_with_alarm": False,
            }
        )

    assert result["type"] is FlowResultType.ABORT
    data = hass.config_entries.async_update_subentry.call_args.kwargs["data"]
    assert "night_entity" not in data
    assert "detector_sensor_1" not in data


@pytest.mark.asyncio
async def test_controller_subentry_reconfigure_form_stays_clear_for_removed_entities(hass) -> None:
    """Reopening a controller with cleared optional entities should not restore them."""
    flow = SwitchManagerControllerSubentryFlow()
    flow.hass = hass
    flow.handler = ("entry-1", SUBENTRY_TYPE_CONTROLLER)
    flow.context = {"source": "reconfigure", "subentry_id": "sub-1"}

    subentry = ConfigSubentry(
        data=MappingProxyType(
            {
                "main_entity": "light.hallway",
                "wait_time": 120,
                "enabled": True,
                "activate_on_detection": True,
                "turn_off_when_presence_clears": False,
                "notify_with_alarm": False,
            }
        ),
        subentry_id="sub-1",
        subentry_type=SUBENTRY_TYPE_CONTROLLER,
        title="Hallway",
        unique_id="hallway",
    )
    entry = SimpleNamespace(subentries={"sub-1": subentry})

    with patch.object(flow, "_get_entry", return_value=entry), patch.object(
        flow, "_get_reconfigure_subentry", return_value=subentry
    ):
        result = await flow.async_step_reconfigure()

    schema = result["data_schema"]
    optional_keys = [key for key in schema.schema if getattr(key, "schema", None) == "night_entity"]
    assert optional_keys
    assert optional_keys[0].default is vol.UNDEFINED


@pytest.mark.asyncio
async def test_controller_subentry_flow_rejects_duplicate_name_entity(hass) -> None:
    """The controller subentry flow should reject a duplicate name entity."""
    flow = SwitchManagerControllerSubentryFlow()
    flow.hass = hass
    flow.handler = ("entry-1", SUBENTRY_TYPE_CONTROLLER)
    flow.context = {"source": "user"}

    existing_subentry = ConfigSubentry(
        data=MappingProxyType(
            {
                "main_entity": "light.hallway",
                "wait_time": 120,
                "enabled": True,
                "activate_on_detection": True,
                "turn_off_when_presence_clears": False,
                "notify_with_alarm": False,
            }
        ),
        subentry_id="sub-1",
        subentry_type=SUBENTRY_TYPE_CONTROLLER,
        title="Hallway",
        unique_id="hallway",
    )

    with patch.object(
        flow,
        "_get_entry",
        return_value=SimpleNamespace(subentries={"sub-1": existing_subentry}),
    ):
        result = await flow.async_step_user(
            {
                "main_entity": "light.hallway",
                "wait_time": 120,
                "enabled": True,
                "activate_on_detection": True,
                "turn_off_when_presence_clears": False,
                "notify_with_alarm": False,
            }
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "controller_name_entity_already_configured"}


@pytest.mark.asyncio
async def test_controller_subentry_flow_rejects_duplicate_night_name_entity(hass) -> None:
    """The selected night entity must not name more than one controller."""
    flow = SwitchManagerControllerSubentryFlow()
    flow.hass = hass
    flow.handler = ("entry-1", SUBENTRY_TYPE_CONTROLLER)
    flow.context = {"source": "user"}
    existing_subentry = ConfigSubentry(
        data=MappingProxyType(
            {
                "main_entity": "light.hallway",
                "night_entity": "light.hallway_night",
                "use_night_entity_name": True,
            }
        ),
        subentry_id="sub-1",
        subentry_type=SUBENTRY_TYPE_CONTROLLER,
        title="Hallway Night",
        unique_id="hallway_night",
    )

    with patch.object(
        flow,
        "_get_entry",
        return_value=SimpleNamespace(subentries={"sub-1": existing_subentry}),
    ):
        result = await flow.async_step_user(
            {
                "main_entity": "light.kitchen",
                "night_entity": "light.hallway_night",
                "use_night_entity_name": True,
                "wait_time": 120,
                "enabled": True,
                "activate_on_detection": False,
                "turn_off_when_presence_clears": False,
                "notify_with_alarm": False,
            }
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "controller_name_entity_already_configured"}


@pytest.mark.asyncio
async def test_controller_subentry_flow_rejects_same_main_and_night_entity(hass) -> None:
    """The controller subentry flow should reject reusing one entity as main and night."""
    flow = SwitchManagerControllerSubentryFlow()
    flow.hass = hass
    flow.handler = ("entry-1", SUBENTRY_TYPE_CONTROLLER)
    flow.context = {"source": "user"}

    with patch.object(flow, "_get_entry", return_value=SimpleNamespace(subentries={})):
        result = await flow.async_step_user(
            {
                "main_entity": "light.hallway",
                "night_entity": "light.hallway",
                "wait_time": 120,
                "enabled": True,
                "activate_on_detection": True,
                "turn_off_when_presence_clears": False,
                "notify_with_alarm": False,
            }
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "main_and_night_entity_must_differ"}


@pytest.mark.asyncio
async def test_controller_subentry_flow_allows_shared_turn_off_target(hass) -> None:
    """Explicit turn-off targets may overlap with another controller's owned entities."""
    flow = SwitchManagerControllerSubentryFlow()
    flow.hass = hass
    flow.handler = ("entry-1", SUBENTRY_TYPE_CONTROLLER)
    flow.context = {"source": "user"}

    existing_subentry = ConfigSubentry(
        data=MappingProxyType(
            {
                "main_entity": "light.hallway",
                "night_entity": "light.hallway_night",
                "wait_time": 120,
                "enabled": True,
                "activate_on_detection": True,
                "turn_off_when_presence_clears": False,
                "notify_with_alarm": False,
            }
        ),
        subentry_id="sub-1",
        subentry_type=SUBENTRY_TYPE_CONTROLLER,
        title="Hallway",
        unique_id="hallway",
    )

    with patch.object(
        flow,
        "_get_entry",
        return_value=SimpleNamespace(subentries={"sub-1": existing_subentry}),
    ):
        result = await flow.async_step_user(
            {
                "main_entity": "light.kitchen",
                "turn_off_entity_1": "light.hallway_night",
                "wait_time": 120,
                "enabled": True,
                "activate_on_detection": True,
                "turn_off_when_presence_clears": False,
                "notify_with_alarm": False,
            }
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.asyncio
async def test_controller_subentry_flow_reconfigure_rejects_same_main_and_night_entity(hass) -> None:
    """Reconfigure should also reject using the same entity for main and night."""
    flow = SwitchManagerControllerSubentryFlow()
    flow.hass = hass
    flow.handler = ("entry-1", SUBENTRY_TYPE_CONTROLLER)
    flow.context = {"source": "reconfigure", "subentry_id": "sub-1"}
    subentry = ConfigSubentry(
        data=MappingProxyType(
            {
                "main_entity": "light.hallway",
                "wait_time": 120,
                "enabled": True,
                "activate_on_detection": True,
                "turn_off_when_presence_clears": False,
                "notify_with_alarm": False,
            }
        ),
        subentry_id="sub-1",
        subentry_type=SUBENTRY_TYPE_CONTROLLER,
        title="Hallway",
        unique_id="hallway",
    )
    entry = SimpleNamespace(subentries={"sub-1": subentry})

    with patch.object(flow, "_get_entry", return_value=entry), patch.object(
        flow, "_get_reconfigure_subentry", return_value=subentry
    ):
        result = await flow.async_step_reconfigure(
            {
                "main_entity": "light.hallway",
                "night_entity": "light.hallway",
                "wait_time": 120,
                "enabled": True,
                "activate_on_detection": True,
                "turn_off_when_presence_clears": False,
                "notify_with_alarm": False,
            }
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "main_and_night_entity_must_differ"}


@pytest.mark.asyncio
async def test_controller_subentry_flow_reconfigure_allows_overlapping_non_name_entity(
    hass,
) -> None:
    """Controllers may share an entity when it is not their selected name source."""
    flow = SwitchManagerControllerSubentryFlow()
    flow.hass = hass
    flow.handler = ("entry-1", SUBENTRY_TYPE_CONTROLLER)
    flow.context = {"source": "reconfigure", "subentry_id": "sub-2"}

    existing_subentry = ConfigSubentry(
        data=MappingProxyType(
            {
                "main_entity": "light.hallway",
                "night_entity": "light.hallway_night",
                "wait_time": 120,
                "enabled": True,
                "activate_on_detection": True,
                "turn_off_when_presence_clears": False,
                "notify_with_alarm": False,
            }
        ),
        subentry_id="sub-1",
        subentry_type=SUBENTRY_TYPE_CONTROLLER,
        title="Hallway",
        unique_id="hallway",
    )
    subentry = ConfigSubentry(
        data=MappingProxyType(
            {
                "main_entity": "light.kitchen",
                "wait_time": 120,
                "enabled": True,
                "activate_on_detection": True,
                "turn_off_when_presence_clears": False,
                "notify_with_alarm": False,
            }
        ),
        subentry_id="sub-2",
        subentry_type=SUBENTRY_TYPE_CONTROLLER,
        title="Kitchen",
        unique_id="kitchen",
    )
    entry = SimpleNamespace(subentries={"sub-1": existing_subentry, "sub-2": subentry})
    hass.config_entries.async_update_subentry = Mock(return_value=True)

    with patch.object(flow, "_get_entry", return_value=entry), patch.object(
        flow, "_get_reconfigure_subentry", return_value=subentry
    ):
        result = await flow.async_step_reconfigure(
            {
                "main_entity": "light.kitchen",
                "night_entity": "light.hallway_night",
                "wait_time": 120,
                "enabled": True,
                "activate_on_detection": True,
                "turn_off_when_presence_clears": False,
                "notify_with_alarm": False,
            }
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


@pytest.mark.asyncio
async def test_controller_subentry_flow_requires_night_entity_for_night_name(hass) -> None:
    """Selecting the night-name option requires a configured night entity."""
    flow = SwitchManagerControllerSubentryFlow()
    flow.hass = hass
    flow.handler = ("entry-1", SUBENTRY_TYPE_CONTROLLER)
    flow.context = {"source": "user"}

    with patch.object(flow, "_get_entry", return_value=SimpleNamespace(subentries={})):
        result = await flow.async_step_user(
            {
                "main_entity": "light.hallway",
                "use_night_entity_name": True,
                "wait_time": 120,
                "enabled": True,
                "activate_on_detection": False,
                "turn_off_when_presence_clears": False,
                "notify_with_alarm": False,
            }
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "night_entity_required_for_name"}


def test_controller_schema_uses_duration_selector_defaults() -> None:
    """Existing wait times should render as duration selector values."""
    assert _wait_time_selector_default(3723) == {
        "hours": 1,
        "minutes": 2,
        "seconds": 3,
    }


@pytest.mark.asyncio
async def test_controller_subentry_flow_normalizes_duration_input(hass) -> None:
    """Duration selector payloads should be stored as seconds."""
    flow = SwitchManagerControllerSubentryFlow()
    flow.hass = hass
    flow.handler = ("entry-1", SUBENTRY_TYPE_CONTROLLER)
    flow.context = {"source": "user"}

    with patch.object(flow, "_get_entry", return_value=SimpleNamespace(subentries={})):
        result = await flow.async_step_user(
            {
                "main_entity": "light.hallway",
                "wait_time": {"hours": 1, "minutes": 2, "seconds": 3},
                "enabled": True,
                "activate_on_detection": True,
                "turn_off_when_presence_clears": False,
                "notify_with_alarm": False,
            }
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["wait_time"] == 3723