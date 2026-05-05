"""Unit tests for config-flow helpers and controller subentry flows."""

from __future__ import annotations

from types import MappingProxyType, SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import ConfigSubentry

from custom_components.switch_manager.config_flow import (
    STEP_GLOBAL_SETTINGS,
    SwitchManagerConfigFlow,
    SwitchManagerControllerSubentryFlow,
    SwitchManagerOptionsFlow,
    _build_controller_id,
    _build_controller_schema,
    _build_global_config_schema,
    _derive_controller_name,
)
from custom_components.switch_manager.const import DOMAIN, SUBENTRY_TYPE_CONTROLLER


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


def test_config_flow_supports_controller_subentries() -> None:
    entry = MockConfigEntry(domain=DOMAIN, title="Switch Manager", data={})
    supported = SwitchManagerConfigFlow.async_get_supported_subentry_types(entry)

    assert supported == {SUBENTRY_TYPE_CONTROLLER: SwitchManagerControllerSubentryFlow}


@pytest.mark.asyncio
async def test_options_flow_init_opens_global_settings(hass) -> None:
    entry = MockConfigEntry(domain=DOMAIN, title="Switch Manager", data={})
    flow = SwitchManagerOptionsFlow(entry)
    flow.hass = hass

    with patch.object(flow, "async_step_global_settings", AsyncMock(return_value={"type": "global"})):
        result = await flow.async_step_init()

    assert result == {"type": "global"}


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
async def test_controller_subentry_user_creates_entry_with_unique_id(hass) -> None:
    flow = SwitchManagerControllerSubentryFlow()
    flow.hass = hass
    flow.handler = ("entry-1", SUBENTRY_TYPE_CONTROLLER)
    flow.context = {"source": "user"}

    existing_subentry = ConfigSubentry(
        data=MappingProxyType({"main_entity": "light.old", "wait_time": 60, "enabled": True}),
        subentry_id="sub-1",
        subentry_type=SUBENTRY_TYPE_CONTROLLER,
        title="Hallway",
        unique_id="hallway",
    )

    with patch.object(flow, "_get_entry", return_value=SimpleNamespace(subentries={"sub-1": existing_subentry})):
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

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Hallway"
    assert result["unique_id"] == "hallway_2"


@pytest.mark.asyncio
async def test_controller_subentry_reconfigure_shows_form_with_defaults(hass) -> None:
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

    with patch.object(flow, "_get_entry", return_value=SimpleNamespace()), patch.object(
        flow, "_get_reconfigure_subentry", return_value=subentry
    ):
        result = await flow.async_step_reconfigure()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"


@pytest.mark.asyncio
async def test_controller_subentry_reconfigure_updates_title_and_data(hass) -> None:
    flow = SwitchManagerControllerSubentryFlow()
    flow.hass = hass
    flow.handler = ("entry-1", SUBENTRY_TYPE_CONTROLLER)
    flow.context = {"source": "reconfigure", "subentry_id": "sub-1"}

    entry = SimpleNamespace()
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
    hass.config_entries.async_update_subentry = Mock(return_value=True)

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