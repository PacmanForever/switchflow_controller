"""Unit tests for config-flow helpers and branchy option steps."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.switch_manager.config_flow import (
    STEP_ADD_CONTROLLER,
    STEP_CONTROLLER_ACTIONS,
    STEP_DELETE_CONTROLLER,
    STEP_EDIT_CONTROLLER,
    STEP_GLOBAL_SETTINGS,
    STEP_SELECT_CONTROLLER,
    SwitchManagerConfigFlow,
    SwitchManagerOptionsFlow,
    _build_controller_id,
    _build_controller_schema,
    _build_controller_select_schema,
    _build_global_config_schema,
    _derive_controller_name,
)
from custom_components.switch_manager.const import DOMAIN
from custom_components.switch_manager.models import ControllerConfig


def _controller(controller_id: str) -> ControllerConfig:
    return ControllerConfig.from_mapping(
        {
            "id": controller_id,
            "name": controller_id.title(),
            "main_entity": f"light.{controller_id}",
            "wait_time": 60,
        }
    )


def test_derive_controller_name_prefers_friendly_name(hass) -> None:
    hass.states.async_set("light.hallway", "off", {"friendly_name": "Hallway Light"})
    assert _derive_controller_name(hass, "light.hallway") == "Hallway Light"


def test_derive_controller_name_falls_back_to_object_id_and_default(hass) -> None:
    assert _derive_controller_name(hass, "light.kitchen_ceiling") == "Kitchen Ceiling"
    assert _derive_controller_name(hass, "light.", fallback="Fallback") == "Fallback"
    assert _derive_controller_name(hass, "light.") == "Controller"


def test_build_controller_id_adds_suffix_for_duplicates() -> None:
    assert _build_controller_id("Hallway", {"hallway"}) == "hallway_2"
    assert _build_controller_id("", set()) == "controller"


def test_schema_builders_accept_expected_payloads() -> None:
    global_schema = _build_global_config_schema({"smart_mode_entity": "binary_sensor.smart"})
    controller_schema = _build_controller_schema(
        {
            "id": "hallway",
            "name": "Hallway",
            "main_entity": "light.hallway",
            "wait_time": 60,
        }
    )
    select_schema = _build_controller_select_schema([_controller("hallway")])

    assert global_schema({"smart_mode_entity": "binary_sensor.smart"})["smart_mode_entity"] == "binary_sensor.smart"
    assert controller_schema(
        {
            "enabled": True,
            "main_entity": "light.hallway",
            "activate_on_detection": True,
            "turn_off_when_presence_clears": False,
            "wait_time": 60,
            "notify_with_alarm": False,
        }
    )["main_entity"] == "light.hallway"
    assert select_schema({"controller_id": "hallway"})["controller_id"] == "hallway"


def test_global_schema_accepts_input_booleans_for_mode_helpers() -> None:
    global_schema = _build_global_config_schema(
        {
            "smart_mode_entity": "input_boolean.smart_mode",
            "night_mode_entity": "input_boolean.night_mode",
        }
    )

    result = global_schema(
        {
            "smart_mode_entity": "input_boolean.smart_mode",
            "night_mode_entity": "input_boolean.night_mode",
        }
    )

    assert result["smart_mode_entity"] == "input_boolean.smart_mode"
    assert result["night_mode_entity"] == "input_boolean.night_mode"


@pytest.mark.asyncio
async def test_user_flow_shows_form_without_input(hass) -> None:
    flow = SwitchManagerConfigFlow()
    flow.hass = hass
    with patch.object(flow, "_async_current_entries", return_value=[]):
        result = await flow.async_step_user()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


@pytest.mark.asyncio
async def test_async_get_options_flow_returns_options_flow() -> None:
    entry = MockConfigEntry(domain=DOMAIN, title="Switch Manager", data={})
    options_flow = SwitchManagerConfigFlow.async_get_options_flow(entry)
    assert isinstance(options_flow, SwitchManagerOptionsFlow)


@pytest.mark.asyncio
async def test_options_flow_init_menu_depends_on_controllers(hass) -> None:
    entry = MockConfigEntry(domain=DOMAIN, title="Switch Manager", data={})
    flow = SwitchManagerOptionsFlow(entry)
    flow.hass = hass

    with patch(
        "custom_components.switch_manager.config_flow.SwitchManagerStorage.async_load",
        AsyncMock(return_value=[]),
    ):
        result = await flow.async_step_init()
    assert result["type"] is FlowResultType.MENU
    assert result["menu_options"] == [STEP_GLOBAL_SETTINGS, STEP_ADD_CONTROLLER]

    with patch(
        "custom_components.switch_manager.config_flow.SwitchManagerStorage.async_load",
        AsyncMock(return_value=[_controller("hallway")]),
    ):
        result = await flow.async_step_init()
    assert result["menu_options"] == [STEP_GLOBAL_SETTINGS, STEP_ADD_CONTROLLER, STEP_SELECT_CONTROLLER]


@pytest.mark.asyncio
async def test_options_flow_global_settings_handles_form_and_save(hass) -> None:
    entry = MockConfigEntry(domain=DOMAIN, title="Switch Manager", data={"smart_mode_entity": "binary_sensor.smart"})
    flow = SwitchManagerOptionsFlow(entry)
    flow.hass = hass

    form_result = await flow.async_step_global_settings()
    assert form_result["type"] is FlowResultType.FORM
    assert form_result["step_id"] == STEP_GLOBAL_SETTINGS

    save_result = await flow.async_step_global_settings({"smart_mode_entity": "binary_sensor.smart"})
    assert save_result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.asyncio
async def test_select_controller_aborts_when_empty_and_advances_when_selected(hass) -> None:
    entry = MockConfigEntry(domain=DOMAIN, title="Switch Manager", data={})
    flow = SwitchManagerOptionsFlow(entry)
    flow.hass = hass

    with patch(
        "custom_components.switch_manager.config_flow.SwitchManagerStorage.async_load",
        AsyncMock(return_value=[]),
    ):
        result = await flow.async_step_select_controller()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_controllers"

    with patch(
        "custom_components.switch_manager.config_flow.SwitchManagerStorage.async_load",
        AsyncMock(return_value=[_controller("hallway")]),
    ):
        form_result = await flow.async_step_select_controller()
        next_result = await flow.async_step_select_controller({"controller_id": "hallway"})

    assert form_result["type"] is FlowResultType.FORM
    assert form_result["step_id"] == STEP_SELECT_CONTROLLER
    assert next_result["type"] is FlowResultType.MENU
    assert flow._selected_controller_id == "hallway"


@pytest.mark.asyncio
async def test_controller_actions_and_delete_cover_redirect_and_submit(hass) -> None:
    entry = MockConfigEntry(domain=DOMAIN, title="Switch Manager", data={})
    flow = SwitchManagerOptionsFlow(entry)
    flow.hass = hass

    with patch.object(flow, "async_step_select_controller", AsyncMock(return_value={"type": "redirect"})):
        result = await flow.async_step_controller_actions()
    assert result == {"type": "redirect"}

    flow._selected_controller_id = "hallway"
    menu_result = await flow.async_step_controller_actions()
    assert menu_result["type"] is FlowResultType.MENU
    assert menu_result["menu_options"] == [STEP_EDIT_CONTROLLER, STEP_DELETE_CONTROLLER]

    with patch.object(flow, "async_step_select_controller", AsyncMock(return_value={"type": "redirect"})):
        flow._selected_controller_id = None
        redirect_result = await flow.async_step_delete_controller()
    assert redirect_result == {"type": "redirect"}

    flow._selected_controller_id = "hallway"
    with (
        patch(
            "custom_components.switch_manager.config_flow.SwitchManagerStorage.async_delete",
            AsyncMock(),
        ) as delete_mock,
        patch.object(hass.config_entries, "async_reload", AsyncMock()),
    ):
        form_result = await flow.async_step_delete_controller()
        submit_result = await flow.async_step_delete_controller({})

    assert form_result["type"] is FlowResultType.FORM
    assert form_result["step_id"] == STEP_DELETE_CONTROLLER
    assert submit_result["type"] is FlowResultType.CREATE_ENTRY
    delete_mock.assert_awaited_once_with("hallway")


@pytest.mark.asyncio
async def test_edit_controller_aborts_when_missing_and_shows_form_when_found(hass) -> None:
    entry = MockConfigEntry(domain=DOMAIN, title="Switch Manager", data={})
    flow = SwitchManagerOptionsFlow(entry)
    flow.hass = hass
    flow._selected_controller_id = "hallway"

    with patch(
        "custom_components.switch_manager.config_flow.SwitchManagerStorage.async_load",
        AsyncMock(return_value=[]),
    ):
        result = await flow.async_step_edit_controller()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "controller_not_found"

    with patch(
        "custom_components.switch_manager.config_flow.SwitchManagerStorage.async_load",
        AsyncMock(return_value=[_controller("hallway")]),
    ):
        result = await flow.async_step_edit_controller()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == STEP_EDIT_CONTROLLER