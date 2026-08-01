"""Component tests for switchflow_controller illuminance behavior."""

from __future__ import annotations

import pytest

from custom_components.switchflow_controller.controller import ControllerRuntime
from custom_components.switchflow_controller.models import ControllerConfig, GlobalConfig


@pytest.mark.asyncio
async def test_high_illuminance_blocks_detection_activation(hass) -> None:
    """Known high illuminance should block activation for that detection cycle."""
    controller = ControllerConfig.from_mapping(
        {
            "id": "hallway",
            "name": "Hallway",
            "main_entity": "light.hallway",
            "illuminance_sensor": "sensor.hallway_lux",
            "illuminance_threshold_lux": 10,
            "wait_time": 60,
        }
    )
    light_calls: list[dict] = []

    async def handle_light_turn_on(call) -> None:
        light_calls.append(call.data)

    hass.services.async_register("light", "turn_on", handle_light_turn_on)
    hass.states.async_set("light.hallway", "off")
    hass.states.async_set("sensor.hallway_lux", "50")

    runtime = ControllerRuntime(hass, GlobalConfig(), controller, "entry-1")
    activated = await runtime._async_run_detection_activation_path()

    assert activated is False
    assert light_calls == []