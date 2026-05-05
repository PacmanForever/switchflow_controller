"""Component tests for switch_manager config and options flows."""

from __future__ import annotations

from types import MappingProxyType
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from homeassistant.config_entries import ConfigSubentry
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.switch_manager.config_flow import (
    SwitchManagerConfigFlow,
    SwitchManagerControllerSubentryFlow,
)
from custom_components.switch_manager.const import DOMAIN, SUBENTRY_TYPE_CONTROLLER


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


@pytest.mark.asyncio
async def test_controller_subentry_flow_reconfigures_existing_controller(hass) -> None:
    """The controller subentry reconfigure flow should update title and data."""
    flow = SwitchManagerControllerSubentryFlow()
    flow.hass = hass
    flow.handler = ("entry-1", SUBENTRY_TYPE_CONTROLLER)
    flow.context = {"source": "reconfigure", "subentry_id": "sub-1"}
    hass.config_entries.async_update_subentry = Mock(return_value=True)
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