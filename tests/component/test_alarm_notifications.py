"""Component tests for switchflow_controller alarm notification behavior."""

from __future__ import annotations

import pytest

from custom_components.switchflow_controller.controller import ControllerRuntime
from custom_components.switchflow_controller.models import ControllerConfig, GlobalConfig


@pytest.mark.asyncio
async def test_alarm_notification_path_turns_on_main_and_calls_script(hass) -> None:
    """Alarm path should turn on the main entity and invoke the configured script."""
    controller = ControllerConfig.from_mapping(
        {
            "id": "hallway",
            "name": "Hallway",
            "main_entity": "light.hallway",
            "detector_sensor_1": "binary_sensor.hallway_motion",
            "wait_time": 60,
            "notify_with_alarm": True,
        }
    )
    global_config = GlobalConfig.from_mapping(
        {
            "alarm_entity": "alarm_control_panel.house",
            "alarm_timer_entity": "timer.house_alarm",
            "alarm_notification_script_entity": "script.notify_alarm",
        }
    )

    light_calls: list[dict] = []
    script_calls: list[dict] = []

    async def handle_light_turn_on(call) -> None:
        light_calls.append(call.data)

    async def handle_script(call) -> None:
        script_calls.append(call.data)

    hass.services.async_register("light", "turn_on", handle_light_turn_on)
    hass.services.async_register("script", "notify_alarm", handle_script)

    hass.states.async_set("light.hallway", "off")
    hass.states.async_set("binary_sensor.hallway_motion", "on")
    hass.states.async_set("alarm_control_panel.house", "armed_away")
    hass.states.async_set("timer.house_alarm", "idle")
    hass.states.async_set("script.notify_alarm", "off")

    runtime = ControllerRuntime(hass, global_config, controller, "entry-1")
    activated = await runtime._async_run_alarm_notification_path()

    assert activated is True
    assert light_calls == [{"entity_id": "light.hallway"}]
    assert script_calls
    assert (
        script_calls[0]["message"]
        == "SwitchFlow Controller alarm notification from Hallway"
    )
    assert script_calls[0]["controller_name"] == "Hallway"
    assert script_calls[0]["trigger_entity_id"] == "binary_sensor.hallway_motion"