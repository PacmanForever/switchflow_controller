"""Component tests for switchflow_controller runtime behavior."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import Event, State

from custom_components.switchflow_controller.controller import ControllerRuntime
from custom_components.switchflow_controller.models import ControllerConfig, GlobalConfig


def test_opening_sensors_are_registered_as_optional_listeners(hass) -> None:
    """Both configured window and door sensors should receive state-change listeners."""
    controller = ControllerConfig.from_mapping(
        {
            "id": "hallway",
            "name": "Hallway",
            "main_entity": "light.hallway",
            "opening_sensor_1": "binary_sensor.hallway_window",
            "opening_sensor_2": "binary_sensor.hallway_door",
            "wait_time": 120,
        }
    )
    runtime = ControllerRuntime(hass, GlobalConfig(), controller, "entry-1")

    assert "binary_sensor.hallway_window" in runtime._configured_listener_entities()
    assert "binary_sensor.hallway_door" in runtime._configured_listener_entities()


@pytest.mark.asyncio
async def test_opening_sensor_event_dispatches_with_its_state_transition(hass) -> None:
    """Opening sensor events should route their old and new states to the alarm path."""
    controller = ControllerConfig.from_mapping(
        {
            "id": "hallway",
            "name": "Hallway",
            "main_entity": "light.hallway",
            "opening_sensor_1": "binary_sensor.hallway_window",
            "wait_time": 120,
        }
    )
    runtime = ControllerRuntime(hass, GlobalConfig(), controller, "entry-1")
    runtime._async_handle_opening_state_change = AsyncMock()
    old_state = State("binary_sensor.hallway_window", "off")
    new_state = State("binary_sensor.hallway_window", "on")

    await runtime._async_handle_optional_entity_event(
        Event(
            "state_changed",
            {
                "entity_id": "binary_sensor.hallway_window",
                "old_state": old_state,
                "new_state": new_state,
            },
        )
    )

    runtime._async_handle_opening_state_change.assert_awaited_once_with(
        "binary_sensor.hallway_window", old_state, new_state
    )


@pytest.mark.asyncio
async def test_main_off_clears_opening_alarm_ownership_and_timer(hass) -> None:
    """Manual main-light shutdown must cancel only the opening alarm timer ownership."""
    controller = ControllerConfig.from_mapping(
        {"id": "hallway", "name": "Hallway", "main_entity": "light.hallway", "wait_time": 120}
    )
    runtime = ControllerRuntime(hass, GlobalConfig(), controller, "entry-1")
    runtime._opening_alarm_owns_main = True
    runtime._async_cancel_opening_alarm_timer = AsyncMock()
    runtime._async_cancel_timer = AsyncMock()

    await runtime._async_handle_main_entity_event(
        Event("state_changed", {"new_state": State("light.hallway", "off")})
    )

    assert runtime._opening_alarm_owns_main is False
    runtime._async_cancel_opening_alarm_timer.assert_awaited_once()
    runtime._async_cancel_timer.assert_awaited_once()


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
async def test_manual_night_on_does_nothing_when_smart_mode_is_disabled(hass) -> None:
    """Manual night-entity activation should be ignored when smart mode is off."""
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
    hass.states.async_set("binary_sensor.smart", "off")

    runtime = ControllerRuntime(
        hass,
        GlobalConfig.from_mapping({"smart_mode_entity": "binary_sensor.smart"}),
        controller,
        "entry-1",
    )
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

    runtime._async_turn_off_configured_entities.assert_not_awaited()
    runtime._async_restart_timer.assert_not_awaited()


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


@pytest.mark.asyncio
async def test_manual_main_on_turns_off_available_secondary_entity(hass) -> None:
    """Manual main activation should still call the secondary turn-off service when available."""
    controller = ControllerConfig.from_mapping(
        {
            "id": "hallway",
            "name": "Hallway",
            "main_entity": "light.hallway",
            "turn_off_entity_1": "light.other",
            "wait_time": 120,
        }
    )
    turn_off_calls: list[dict] = []

    async def handle_light_turn_off(call) -> None:
        turn_off_calls.append(call.data)

    hass.services.async_register("light", "turn_off", handle_light_turn_off)
    hass.states.async_set("light.other", "on")

    runtime = ControllerRuntime(hass, GlobalConfig(), controller, "entry-1")
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

    assert turn_off_calls == [{"entity_id": "light.other"}]
    runtime._async_restart_timer.assert_awaited_once()


@pytest.mark.asyncio
async def test_manual_main_on_skips_unavailable_secondary_entity(hass) -> None:
    """Manual main activation should not call turn-off services for unavailable secondaries."""
    controller = ControllerConfig.from_mapping(
        {
            "id": "hallway",
            "name": "Hallway",
            "main_entity": "light.hallway",
            "turn_off_entity_1": "light.other",
            "wait_time": 120,
        }
    )
    turn_off_calls: list[dict] = []

    async def handle_light_turn_off(call) -> None:
        turn_off_calls.append(call.data)

    hass.services.async_register("light", "turn_off", handle_light_turn_off)
    hass.states.async_set("light.other", STATE_UNAVAILABLE)

    runtime = ControllerRuntime(hass, GlobalConfig(), controller, "entry-1")
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

    assert turn_off_calls == []
    runtime._async_restart_timer.assert_awaited_once()


@pytest.mark.asyncio
async def test_detector_activity_restarts_timer_when_controlled_entity_is_already_on(hass) -> None:
    """Detector activity should extend an active controller even without reactivation."""
    controller = ControllerConfig.from_mapping(
        {
            "id": "hallway",
            "name": "Hallway",
            "main_entity": "light.hallway",
            "detector_sensor_1": "binary_sensor.hallway_presence",
            "activate_on_detection": False,
            "wait_time": 120,
        }
    )
    hass.states.async_set("light.hallway", "on")

    runtime = ControllerRuntime(hass, GlobalConfig(), controller, "entry-1")
    runtime._async_run_alarm_notification_path = AsyncMock(return_value=False)
    runtime._async_restart_timer = AsyncMock()

    await runtime._async_handle_detector_state_change(
        State(
            "binary_sensor.hallway_presence",
            "on",
            {"device_class": "presence"},
        )
    )

    runtime._async_restart_timer.assert_awaited_once()


@pytest.mark.asyncio
async def test_manual_main_on_does_nothing_when_smart_mode_is_disabled(hass) -> None:
    """Manual main-entity activation should be ignored when smart mode is off."""
    controller = ControllerConfig.from_mapping(
        {
            "id": "hallway",
            "name": "Hallway",
            "main_entity": "light.hallway",
            "turn_off_entity_1": "light.other",
            "wait_time": 120,
        }
    )
    hass.states.async_set("binary_sensor.smart", "off")

    runtime = ControllerRuntime(
        hass,
        GlobalConfig.from_mapping({"smart_mode_entity": "binary_sensor.smart"}),
        controller,
        "entry-1",
    )
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

    runtime._async_turn_off_configured_entities.assert_not_awaited()
    runtime._async_restart_timer.assert_not_awaited()


@pytest.mark.asyncio
async def test_manual_main_off_turns_off_night_too(hass) -> None:
    """Turning off the main entity manually should also turn off the night entity."""
    controller = ControllerConfig.from_mapping(
        {
            "id": "hallway",
            "name": "Hallway",
            "main_entity": "light.hallway",
            "night_entity": "light.hallway_night",
            "wait_time": 120,
        }
    )
    hass.states.async_set("light.hallway_night", "on")

    runtime = ControllerRuntime(hass, GlobalConfig(), controller, "entry-1")
    runtime._async_cancel_timer = AsyncMock()
    runtime._async_turn_off_entity = AsyncMock()

    await runtime._async_handle_main_entity_event(
        Event(
            "state_changed",
            {
                "entity_id": "light.hallway",
                "new_state": State("light.hallway", "off"),
            },
        )
    )

    runtime._async_cancel_timer.assert_awaited_once()
    runtime._async_turn_off_entity.assert_awaited_once_with("light.hallway_night")


@pytest.mark.asyncio
async def test_manual_night_off_turns_off_main_too(hass) -> None:
    """Turning off the night entity manually should also turn off the main entity."""
    controller = ControllerConfig.from_mapping(
        {
            "id": "hallway",
            "name": "Hallway",
            "main_entity": "light.hallway",
            "night_entity": "light.hallway_night",
            "wait_time": 120,
        }
    )
    hass.states.async_set("light.hallway", "on")

    runtime = ControllerRuntime(hass, GlobalConfig(), controller, "entry-1")
    runtime._async_cancel_timer = AsyncMock()
    runtime._async_turn_off_entity = AsyncMock()

    await runtime._async_handle_optional_entity_event(
        Event(
            "state_changed",
            {
                "entity_id": "light.hallway_night",
                "new_state": State("light.hallway_night", "off"),
            },
        )
    )

    runtime._async_cancel_timer.assert_awaited_once()
    runtime._async_turn_off_entity.assert_awaited_once_with("light.hallway")


@pytest.mark.asyncio
async def test_smart_mode_disabled_cancels_existing_timer(hass) -> None:
    """Disabling smart mode should stop any running automation timer."""
    controller = ControllerConfig.from_mapping(
        {
            "id": "hallway",
            "name": "Hallway",
            "main_entity": "light.hallway",
            "wait_time": 120,
        }
    )

    runtime = ControllerRuntime(
        hass,
        GlobalConfig.from_mapping({"smart_mode_entity": "binary_sensor.smart"}),
        controller,
        "entry-1",
    )
    runtime._async_cancel_timer = AsyncMock()

    await runtime._async_handle_optional_entity_event(
        Event(
            "state_changed",
            {
                "entity_id": "binary_sensor.smart",
                "new_state": State("binary_sensor.smart", "off"),
            },
        )
    )

    runtime._async_cancel_timer.assert_awaited_once()


@pytest.mark.asyncio
async def test_async_start_does_not_restore_timer_when_smart_mode_is_disabled(hass) -> None:
    """Startup should not restore a controller timer while smart mode is off."""
    controller = ControllerConfig.from_mapping(
        {
            "id": "hallway",
            "name": "Hallway",
            "main_entity": "light.hallway",
            "wait_time": 120,
        }
    )
    hass.states.async_set("binary_sensor.smart", "off")
    hass.states.async_set("light.hallway", "on")

    runtime = ControllerRuntime(
        hass,
        GlobalConfig.from_mapping({"smart_mode_entity": "binary_sensor.smart"}),
        controller,
        "entry-1",
    )
    runtime._async_restart_timer = AsyncMock()

    await runtime.async_start()

    runtime._async_restart_timer.assert_not_awaited()