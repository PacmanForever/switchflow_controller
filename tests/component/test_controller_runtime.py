"""Component tests for switch_manager runtime behavior."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from homeassistant.core import Event, State

from custom_components.switch_manager.controller import ControllerRuntime
from custom_components.switch_manager.models import ControllerConfig, GlobalConfig


@pytest.mark.asyncio
async def test_detector_clear_turns_off_entities_early(hass) -> None:
    """Configured detectors should turn off entities early when all are clear."""
    controller = ControllerConfig.from_mapping(
        {
            "id": "hallway",
            "name": "Hallway",
            "main_entity": "light.hallway",
            "night_entity": "light.hallway_night",
            "detector_sensor_1": "binary_sensor.hallway_presence_1",
            "detector_sensor_2": "binary_sensor.hallway_presence_2",
            "wait_time": 120,
            "turn_off_when_presence_clears": True,
        }
    )
    hass.states.async_set("light.hallway", "on")
    hass.states.async_set("light.hallway_night", "on")
    hass.states.async_set(
        "binary_sensor.hallway_presence_1",
        "off",
        {"device_class": "presence"},
    )
    hass.states.async_set(
        "binary_sensor.hallway_presence_2",
        "off",
        {"device_class": "presence"},
    )

    runtime = ControllerRuntime(hass, GlobalConfig(), controller, "entry-1")
    runtime._async_turn_off_entity = AsyncMock()

    await runtime._async_handle_detector_state_change(
        State(
            "binary_sensor.hallway_presence_1",
            "off",
            {"device_class": "presence"},
        )
    )

    assert runtime._async_turn_off_entity.await_count == 2
    assert runtime._async_turn_off_entity.await_args_list[0].args[0] == "light.hallway"
    assert runtime._async_turn_off_entity.await_args_list[1].args[0] == "light.hallway_night"


@pytest.mark.asyncio
async def test_manual_night_on_restarts_timer_and_turns_off_secondaries(hass) -> None:
    """Manual night-entity activation should still participate in controller timing."""
    controller = ControllerConfig.from_mapping(
        {
            "id": "hallway",
            "name": "Hallway",
            "main_entity": "light.hallway",
            "night_entity": "light.hallway_night",
            "turn_off_entity_1": "light.other",
            "wait_time": 120,
        }
    )
    runtime = ControllerRuntime(hass, GlobalConfig(), controller, "entry-1")
    runtime._async_turn_off_configured_entities = AsyncMock()
    runtime._async_restart_timer = AsyncMock()

    await runtime._async_handle_optional_entity_event(
        Event(
            "state_changed",
            {
                "entity_id": "light.hallway_night",
                "new_state": State("light.hallway_night", "on"),
            },
        )
    )

    runtime._async_turn_off_configured_entities.assert_awaited_once()
    runtime._async_restart_timer.assert_awaited_once()


@pytest.mark.asyncio
async def test_manual_main_on_restarts_timer_and_turns_off_secondaries(hass) -> None:
    """Manual main-entity activation should still participate in controller timing."""
    controller = ControllerConfig.from_mapping(
        {
            "id": "hallway",
            "name": "Hallway",
            "main_entity": "light.hallway",
            "turn_off_entity_1": "light.other",
            "wait_time": 120,
        }
    )
    runtime = ControllerRuntime(hass, GlobalConfig(), controller, "entry-1")
    runtime._async_turn_off_configured_entities = AsyncMock()
    runtime._async_restart_timer = AsyncMock()

    await runtime._async_handle_main_entity_event(
        Event(
            "state_changed",
            {
                "entity_id": "light.hallway",
                "new_state": State("light.hallway", "on"),
            },
        )
    )

    runtime._async_turn_off_configured_entities.assert_awaited_once_with(["light.other", None])
    runtime._async_restart_timer.assert_awaited_once()