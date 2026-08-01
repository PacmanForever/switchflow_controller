"""Component tests for switchflow_controller alarm notification behavior."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from homeassistant.core import State

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
        == "SwitchFlow Controller alarm: motion detected in Hallway"
    )
    assert script_calls[0]["controller_name"] == "Hallway"
    assert script_calls[0]["trigger_entity_id"] == "binary_sensor.hallway_motion"


@pytest.mark.asyncio
async def test_armed_motion_uses_opening_alarm_light_timer(hass) -> None:
    """An armed motion alarm response uses the global opening-light duration."""
    controller = ControllerConfig.from_mapping(
        {
            "id": "hallway",
            "name": "Hallway",
            "main_entity": "light.hallway",
            "detector_sensor_1": "binary_sensor.hallway_motion",
            "wait_time": 600,
            "notify_with_alarm": True,
        }
    )
    global_config = GlobalConfig.from_mapping(
        {
            "alarm_entity": "alarm_control_panel.house",
            "alarm_notification_script_entity": "script.notify_alarm",
            "opening_alarm_light_duration": 60,
        }
    )

    hass.services.async_register("script", "notify_alarm", AsyncMock())
    hass.states.async_set("light.hallway", "off")
    hass.states.async_set("binary_sensor.hallway_motion", "on")
    hass.states.async_set("alarm_control_panel.house", "armed_away")
    hass.states.async_set("script.notify_alarm", "off")
    runtime = ControllerRuntime(hass, global_config, controller, "entry-1")
    runtime._async_turn_on_entity = AsyncMock()
    runtime._async_cancel_timer = AsyncMock()
    runtime._async_restart_timer = AsyncMock()
    runtime._async_restart_opening_alarm_timer = AsyncMock()

    await runtime._async_handle_detector_state_change(
        State("binary_sensor.hallway_motion", "on")
    )

    runtime._async_turn_on_entity.assert_awaited_once_with("light.hallway")
    runtime._async_cancel_timer.assert_awaited_once()
    runtime._async_restart_opening_alarm_timer.assert_awaited_once()
    runtime._async_restart_timer.assert_not_awaited()
    assert runtime._opening_alarm_owns_main is True


@pytest.mark.asyncio
async def test_normal_motion_uses_controller_wait_timer(hass) -> None:
    """A non-alarm motion activation retains the controller wait timer."""
    controller = ControllerConfig.from_mapping(
        {
            "id": "hallway",
            "name": "Hallway",
            "main_entity": "light.hallway",
            "detector_sensor_1": "binary_sensor.hallway_motion",
            "wait_time": 600,
            "activate_on_detection": True,
        }
    )
    runtime = ControllerRuntime(hass, GlobalConfig(), controller, "entry-1")
    runtime._async_run_alarm_notification_path = AsyncMock(return_value=False)
    runtime._async_run_detection_activation_path = AsyncMock(return_value=True)
    runtime._async_restart_timer = AsyncMock()
    runtime._async_restart_opening_alarm_timer = AsyncMock()
    hass.states.async_set("light.hallway", "off")

    await runtime._async_handle_detector_state_change(
        State("binary_sensor.hallway_motion", "on")
    )

    runtime._async_restart_timer.assert_awaited_once()
    runtime._async_restart_opening_alarm_timer.assert_not_awaited()
    assert runtime._opening_alarm_owns_main is False


@pytest.mark.asyncio
async def test_opening_alarm_notifies_and_owns_an_off_main_light(hass) -> None:
    """An armed window opening notifies and starts its own light timer."""
    controller = ControllerConfig.from_mapping(
        {
            "id": "hallway",
            "name": "Hallway",
            "main_entity": "light.hallway",
            "opening_sensor_1": "binary_sensor.hallway_window",
            "wait_time": 60,
            "notify_with_alarm": False,
        }
    )
    global_config = GlobalConfig.from_mapping(
        {
            "alarm_entity": "alarm_control_panel.house",
            "alarm_notification_script_entity": "script.notify_alarm",
        }
    )
    script_calls: list[dict] = []

    async def handle_script(call) -> None:
        script_calls.append(call.data)

    hass.services.async_register("script", "notify_alarm", handle_script)
    hass.states.async_set("light.hallway", "off")
    hass.states.async_set("alarm_control_panel.house", "armed_away")
    hass.states.async_set("script.notify_alarm", "off")
    runtime = ControllerRuntime(hass, global_config, controller, "entry-1")
    runtime._async_turn_on_entity = AsyncMock()
    runtime._async_restart_opening_alarm_timer = AsyncMock()

    await runtime._async_handle_opening_state_change(
        "binary_sensor.hallway_window",
        State("binary_sensor.hallway_window", "off"),
        State("binary_sensor.hallway_window", "on"),
    )

    runtime._async_turn_on_entity.assert_awaited_once_with("light.hallway")
    runtime._async_restart_opening_alarm_timer.assert_awaited_once()
    assert runtime._opening_alarm_owns_main is True
    assert (
        script_calls[0]["message"]
        == "SwitchFlow Controller alarm: window or door opened in Hallway"
    )
    assert script_calls[0]["trigger_entity_id"] == "binary_sensor.hallway_window"


@pytest.mark.asyncio
async def test_opening_alarm_does_not_time_a_light_already_on(hass) -> None:
    """An opening only notifies when the main light was already on externally."""
    controller = ControllerConfig.from_mapping(
        {
            "id": "hallway",
            "name": "Hallway",
            "main_entity": "light.hallway",
            "opening_sensor_1": "binary_sensor.hallway_window",
            "wait_time": 60,
        }
    )
    global_config = GlobalConfig.from_mapping({"alarm_entity": "alarm_control_panel.house"})
    hass.states.async_set("light.hallway", "on")
    hass.states.async_set("alarm_control_panel.house", "armed_home")
    runtime = ControllerRuntime(hass, global_config, controller, "entry-1")
    runtime._async_turn_on_entity = AsyncMock()
    runtime._async_restart_opening_alarm_timer = AsyncMock()

    await runtime._async_handle_opening_state_change(
        "binary_sensor.hallway_window",
        State("binary_sensor.hallway_window", "off"),
        State("binary_sensor.hallway_window", "on"),
    )

    runtime._async_turn_on_entity.assert_not_awaited()
    runtime._async_restart_opening_alarm_timer.assert_not_awaited()
    assert runtime._opening_alarm_owns_main is False


@pytest.mark.asyncio
async def test_opening_alarm_restarts_only_its_owned_timer(hass) -> None:
    """A second armed opening extends the timer only when the runtime owns the light."""
    controller = ControllerConfig.from_mapping(
        {
            "id": "hallway",
            "name": "Hallway",
            "main_entity": "light.hallway",
            "opening_sensor_2": "binary_sensor.hallway_door",
            "wait_time": 60,
        }
    )
    global_config = GlobalConfig.from_mapping({"alarm_entity": "alarm_control_panel.house"})
    hass.states.async_set("alarm_control_panel.house", "armed_night")
    runtime = ControllerRuntime(hass, global_config, controller, "entry-1")
    runtime._opening_alarm_owns_main = True
    runtime._async_restart_opening_alarm_timer = AsyncMock()

    await runtime._async_handle_opening_state_change(
        "binary_sensor.hallway_door",
        State("binary_sensor.hallway_door", "off"),
        State("binary_sensor.hallway_door", "on"),
    )

    runtime._async_restart_opening_alarm_timer.assert_awaited_once()


@pytest.mark.asyncio
async def test_opening_alarm_timer_only_turns_off_its_owned_light(hass, monkeypatch) -> None:
    """Opening timer expiry turns off the main entity only while it owns it."""
    controller = ControllerConfig.from_mapping(
        {
            "id": "hallway",
            "name": "Hallway",
            "main_entity": "light.hallway",
            "wait_time": 60,
        }
    )
    runtime = ControllerRuntime(hass, GlobalConfig(), controller, "entry-1")
    runtime._opening_alarm_owns_main = True
    runtime._opening_alarm_timer_task = object()
    runtime._async_turn_off_entity = AsyncMock()

    async def immediate_sleep(_seconds: int) -> None:
        return None

    with monkeypatch.context() as context:
        context.setattr(
            "custom_components.switchflow_controller.controller.asyncio.sleep",
            immediate_sleep,
        )
        await runtime._async_opening_alarm_timer_worker()

    runtime._async_turn_off_entity.assert_awaited_once_with("light.hallway")
    assert runtime._opening_alarm_owns_main is False


@pytest.mark.asyncio
async def test_opening_alarm_ignores_non_opening_and_disarmed_events(hass) -> None:
    """Only an off-to-on transition while armed may start the opening alarm path."""
    controller = ControllerConfig.from_mapping(
        {
            "id": "hallway",
            "name": "Hallway",
            "main_entity": "light.hallway",
            "wait_time": 60,
        }
    )
    runtime = ControllerRuntime(
        hass,
        GlobalConfig.from_mapping({"alarm_entity": "alarm_control_panel.house"}),
        controller,
        "entry-1",
    )
    runtime._async_send_alarm_notification = AsyncMock()
    runtime._async_turn_on_entity = AsyncMock()
    hass.states.async_set("alarm_control_panel.house", "disarmed")

    await runtime._async_handle_opening_state_change(
        "binary_sensor.hallway_window",
        State("binary_sensor.hallway_window", "on"),
        State("binary_sensor.hallway_window", "on"),
    )
    await runtime._async_handle_opening_state_change(
        "binary_sensor.hallway_window",
        State("binary_sensor.hallway_window", "off"),
        State("binary_sensor.hallway_window", "on"),
    )

    runtime._async_send_alarm_notification.assert_not_awaited()
    runtime._async_turn_on_entity.assert_not_awaited()


@pytest.mark.asyncio
async def test_opening_alarm_timer_cancellation_cleans_up_task(hass) -> None:
    """Cancelling an active opening timer must not leave an orphaned task."""
    controller = ControllerConfig.from_mapping(
        {"id": "hallway", "name": "Hallway", "main_entity": "light.hallway", "wait_time": 60}
    )
    runtime = ControllerRuntime(hass, GlobalConfig(), controller, "entry-1")

    async def parked_worker() -> None:
        await asyncio.Future()

    task = hass.async_create_task(parked_worker())
    runtime._opening_alarm_timer_task = task
    await runtime._async_cancel_opening_alarm_timer()

    assert task.cancelled()
    assert runtime._opening_alarm_timer_task is None