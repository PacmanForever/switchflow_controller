"""Component tests for switch_manager delayed shutoff behavior."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from homeassistant.core import State

from custom_components.switch_manager.controller import ControllerRuntime
from custom_components.switch_manager.models import ControllerConfig, GlobalConfig


@pytest.mark.asyncio
async def test_mixed_detector_types_turn_off_early_when_all_clear(hass) -> None:
    """Mixed presence and motion detectors should still turn off early when all clear."""
    controller = ControllerConfig.from_mapping(
        {
            "id": "hallway",
            "name": "Hallway",
            "main_entity": "light.hallway",
            "detector_sensor_1": "binary_sensor.hallway_presence",
            "detector_sensor_2": "binary_sensor.hallway_motion",
            "wait_time": 60,
            "turn_off_when_presence_clears": True,
        }
    )
    hass.states.async_set("light.hallway", "on")
    hass.states.async_set(
        "binary_sensor.hallway_presence",
        "off",
        {"device_class": "presence"},
    )
    hass.states.async_set(
        "binary_sensor.hallway_motion",
        "off",
        {"device_class": "motion"},
    )

    runtime = ControllerRuntime(hass, GlobalConfig(), controller, "entry-1")
    runtime._async_turn_off_entity = AsyncMock()

    await runtime._async_handle_detector_state_change(
        State(
            "binary_sensor.hallway_presence",
            "off",
            {"device_class": "presence"},
        )
    )

    assert runtime._async_turn_off_entity.await_count == 1
    assert runtime._async_turn_off_entity.await_args_list[0].args[0] == "light.hallway"


@pytest.mark.asyncio
async def test_timer_expiry_restarts_when_detector_stays_on(hass, monkeypatch) -> None:
    """An active detector at timer expiry should extend the controller instead of turning it off."""
    controller = ControllerConfig.from_mapping(
        {
            "id": "hallway",
            "name": "Hallway",
            "main_entity": "light.hallway",
            "detector_sensor_1": "binary_sensor.hallway_presence",
            "wait_time": 60,
        }
    )
    hass.states.async_set("binary_sensor.hallway_presence", "on", {"device_class": "presence"})

    runtime = ControllerRuntime(hass, GlobalConfig(), controller, "entry-1")
    runtime._async_turn_off_controlled_entities = AsyncMock()
    runtime._async_restart_timer = AsyncMock()

    async def immediate_sleep(_seconds: int) -> None:
        return None

    monkeypatch.setattr("custom_components.switch_manager.controller.asyncio.sleep", immediate_sleep)
    runtime._timer_task = object()

    await runtime._async_timer_worker()

    runtime._async_restart_timer.assert_awaited_once()
    runtime._async_turn_off_controlled_entities.assert_not_awaited()
    assert runtime._timer_task is None