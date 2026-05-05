"""Unit tests for controller helper branches."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from homeassistant.const import STATE_IDLE
from homeassistant.core import Event, State

from custom_components.switch_manager.controller import ControllerRuntime
from custom_components.switch_manager.models import ControllerConfig, GlobalConfig


def _controller(**overrides) -> ControllerConfig:
    payload = {
        "id": "hallway",
        "name": "Hallway",
        "main_entity": "light.hallway",
        "wait_time": 60,
        "enabled": True,
        "activate_on_detection": True,
        "turn_off_when_presence_clears": False,
        "notify_with_alarm": False,
    }
    payload.update(overrides)
    return ControllerConfig.from_mapping(payload)


@pytest.mark.asyncio
async def test_async_start_and_stop_manage_listeners_and_cleanup(hass, monkeypatch) -> None:
    """Start should register listeners and stop should unsubscribe them."""

    controller = _controller(
        night_entity="light.night",
        detector_sensor_1="binary_sensor.motion1",
        detector_sensor_2="binary_sensor.motion2",
    )
    runtime = ControllerRuntime(hass, GlobalConfig(), controller, "entry-1")
    runtime._validate_configured_entities = Mock()
    unsubscribers: list[Mock] = []

    def fake_track_state_change_event(hass, entity_ids, callback):
        unsubscribe = Mock()
        unsubscribers.append(unsubscribe)
        return unsubscribe

    monkeypatch.setattr(
        "custom_components.switch_manager.controller.async_track_state_change_event",
        fake_track_state_change_event,
    )

    await runtime.async_start()
    await runtime.async_stop()

    runtime._validate_configured_entities.assert_called_once()
    assert len(unsubscribers) == 4
    for unsubscribe in unsubscribers:
        unsubscribe.assert_called_once()


@pytest.mark.asyncio
async def test_force_operations_delegate_to_helper_paths(hass) -> None:
    """Force helpers should use the underlying controller methods."""

    runtime = ControllerRuntime(hass, GlobalConfig(), _controller(), "entry-1")
    runtime._async_run_detection_activation_path = AsyncMock(return_value=False)
    runtime._async_turn_on_entity = AsyncMock()
    runtime._async_restart_timer = AsyncMock()
    runtime._async_cancel_timer = AsyncMock()
    runtime._async_turn_off_controlled_entities = AsyncMock()

    await runtime.async_force_turn_on()
    await runtime.async_force_turn_off()
    await runtime.async_reset_timer()

    runtime._async_turn_on_entity.assert_awaited_once_with("light.hallway")
    assert runtime._async_restart_timer.await_count == 2
    runtime._async_cancel_timer.assert_awaited_once()
    runtime._async_turn_off_controlled_entities.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_main_entity_event_covers_on_off_and_missing_state(hass) -> None:
    """Main entity changes should shut secondaries down and cancel timers correctly."""

    controller = _controller(
        night_entity="light.night",
        turn_off_entity_1="switch.a",
        turn_off_entity_2="light.b",
    )
    hass.states.async_set("light.night", "on")
    runtime = ControllerRuntime(hass, GlobalConfig(), controller, "entry-1")
    runtime._async_turn_off_configured_entities = AsyncMock()
    runtime._async_restart_timer = AsyncMock()
    runtime._async_cancel_timer = AsyncMock()
    runtime._async_turn_off_entity = AsyncMock()

    await runtime._async_handle_main_entity_event(Event("state_changed", {"entity_id": "light.hallway", "new_state": None}))
    await runtime._async_handle_main_entity_event(
        Event("state_changed", {"entity_id": "light.hallway", "new_state": State("light.hallway", "on")})
    )
    await runtime._async_handle_main_entity_event(
        Event("state_changed", {"entity_id": "light.hallway", "new_state": State("light.hallway", "off")})
    )

    runtime._async_turn_off_configured_entities.assert_awaited_once_with(["switch.a", "light.b"])
    runtime._async_restart_timer.assert_awaited_once()
    runtime._async_cancel_timer.assert_awaited_once()
    runtime._async_turn_off_entity.assert_awaited_once_with("light.night")


@pytest.mark.asyncio
async def test_optional_entity_events_cover_detector_ignore_and_night_off(hass) -> None:
    """Optional entity handling should delegate correctly across branches."""

    controller = _controller(
        night_entity="light.night",
        detector_sensor_1="binary_sensor.motion1",
    )
    runtime = ControllerRuntime(hass, GlobalConfig(), controller, "entry-1")
    runtime._async_handle_detector_state_change = AsyncMock()
    runtime._async_cancel_timer = AsyncMock()
    runtime._async_is_entity_on = AsyncMock(return_value=False)

    await runtime._async_handle_optional_entity_event(
        Event("state_changed", {"entity_id": "binary_sensor.motion1", "new_state": State("binary_sensor.motion1", "on")})
    )
    await runtime._async_handle_optional_entity_event(
        Event("state_changed", {"entity_id": "switch.other", "new_state": State("switch.other", "on")})
    )
    await runtime._async_handle_optional_entity_event(
        Event("state_changed", {"entity_id": "light.night", "new_state": State("light.night", "off")})
    )

    runtime._async_handle_detector_state_change.assert_awaited_once()
    runtime._async_cancel_timer.assert_awaited_once()


@pytest.mark.asyncio
async def test_detector_on_branch_respects_smart_mode_and_restart_logic(hass) -> None:
    """Detector activation should short-circuit when smart mode is off and restart timer when activated."""

    runtime = ControllerRuntime(hass, GlobalConfig(), _controller(), "entry-1")
    runtime._is_smart_mode_enabled = Mock(side_effect=[False, True])
    runtime._async_run_alarm_notification_path = AsyncMock(return_value=False)
    runtime._async_run_detection_activation_path = AsyncMock(return_value=True)
    runtime._async_restart_timer = AsyncMock()

    await runtime._async_handle_detector_state_change(State("binary_sensor.motion", "on"))
    await runtime._async_handle_detector_state_change(State("binary_sensor.motion", "on"))

    runtime._async_run_alarm_notification_path.assert_awaited_once()
    runtime._async_run_detection_activation_path.assert_awaited_once()
    runtime._async_restart_timer.assert_awaited_once()


@pytest.mark.asyncio
async def test_detector_clear_turns_off_even_without_running_timer(hass) -> None:
    """Detector-clear shutdown should not depend on an active timer task."""

    runtime = ControllerRuntime(
        hass,
        GlobalConfig(),
        _controller(turn_off_when_presence_clears=True, detector_sensor_1="binary_sensor.motion1"),
        "entry-1",
    )
    runtime._async_all_detectors_are_clear = AsyncMock(return_value=True)
    runtime._async_turn_off_controlled_entities = AsyncMock()
    runtime._async_cancel_timer = AsyncMock()

    await runtime._async_handle_detector_state_change(State("binary_sensor.motion1", "off"))

    runtime._async_turn_off_controlled_entities.assert_awaited_once()
    runtime._async_cancel_timer.assert_awaited_once()


def test_is_smart_mode_enabled_reads_global_entity(hass) -> None:
    """Smart mode should default to enabled and respect helper state when configured."""

    controller = _controller()
    assert ControllerRuntime(hass, GlobalConfig(), controller, "entry-1")._is_smart_mode_enabled() is True

    runtime = ControllerRuntime(
        hass,
        GlobalConfig.from_mapping({"smart_mode_entity": "binary_sensor.smart"}),
        controller,
        "entry-1",
    )
    hass.states.async_set("binary_sensor.smart", "off")
    assert runtime._is_smart_mode_enabled() is False
    hass.states.async_set("binary_sensor.smart", "on")
    assert runtime._is_smart_mode_enabled() is True


@pytest.mark.asyncio
async def test_alarm_notification_negative_branches_and_script_unavailable(hass) -> None:
    """Alarm notification should fail closed across all guard branches."""

    base_controller = _controller(notify_with_alarm=True, detector_sensor_1="binary_sensor.motion1")
    hass.states.async_set("binary_sensor.motion1", "on")

    assert await ControllerRuntime(hass, GlobalConfig(), _controller(), "entry-1")._async_run_alarm_notification_path() is False
    assert await ControllerRuntime(hass, GlobalConfig(), base_controller, "entry-1")._async_run_alarm_notification_path() is False

    runtime = ControllerRuntime(
        hass,
        GlobalConfig.from_mapping({"alarm_entity": "alarm_control_panel.house"}),
        base_controller,
        "entry-1",
    )
    hass.states.async_set("alarm_control_panel.house", "disarmed")
    assert await runtime._async_run_alarm_notification_path() is False

    runtime = ControllerRuntime(
        hass,
        GlobalConfig.from_mapping(
            {
                "alarm_entity": "alarm_control_panel.house",
                "alarm_timer_entity": "timer.house",
                "alarm_notification_script_entity": "script.notify_alarm",
            }
        ),
        base_controller,
        "entry-1",
    )
    hass.states.async_set("alarm_control_panel.house", "armed_away")
    hass.states.async_set("timer.house", "active")
    assert await runtime._async_run_alarm_notification_path() is False

    hass.states.async_set("timer.house", STATE_IDLE)
    light_calls: list[dict] = []

    async def handle_light_turn_on(call) -> None:
        light_calls.append(call.data)

    hass.services.async_register("light", "turn_on", handle_light_turn_on)
    activated = await runtime._async_run_alarm_notification_path()
    assert activated is True
    assert light_calls == [{"entity_id": "light.hallway"}]


@pytest.mark.asyncio
async def test_detection_activation_path_covers_night_illuminance_and_fallback(hass) -> None:
    """Detection path should cover night mode, illuminance, and plain fallback branches."""

    hass.services.async_register("light", "turn_on", AsyncMock())
    hass.states.async_set("binary_sensor.night", "on")
    hass.states.async_set("light.hallway", "off")
    hass.states.async_set("light.night", "off")

    runtime = ControllerRuntime(
        hass,
        GlobalConfig.from_mapping({"night_mode_entity": "binary_sensor.night"}),
        _controller(night_entity="light.night"),
        "entry-1",
    )
    runtime._async_turn_on_entity = AsyncMock()
    activated = await runtime._async_run_detection_activation_path()
    assert activated is True
    runtime._async_turn_on_entity.assert_awaited_once_with("light.night")

    runtime = ControllerRuntime(hass, GlobalConfig(), _controller(), "entry-1")
    runtime._async_evaluate_illuminance_rule = AsyncMock(return_value=True)
    runtime._async_turn_on_entity = AsyncMock()
    activated = await runtime._async_run_detection_activation_path()
    assert activated is True
    runtime._async_turn_on_entity.assert_awaited_once_with("light.hallway")

    hass.states.async_set("light.hallway", "on")
    runtime = ControllerRuntime(hass, GlobalConfig(), _controller(night_entity="light.night"), "entry-1")
    runtime._async_evaluate_illuminance_rule = AsyncMock(return_value=False)
    assert await runtime._async_run_detection_activation_path() is True

    hass.states.async_set("light.hallway", "off")
    runtime = ControllerRuntime(hass, GlobalConfig(), _controller(), "entry-1")
    runtime._async_evaluate_illuminance_rule = AsyncMock(return_value=None)
    runtime._async_turn_on_entity = AsyncMock()
    assert await runtime._async_run_detection_activation_path() is True


@pytest.mark.asyncio
async def test_timer_helpers_turn_off_entities_and_clear_task(hass, monkeypatch) -> None:
    """Timer helpers should create, cancel, and finish safely."""

    runtime = ControllerRuntime(hass, GlobalConfig(), _controller(night_entity="light.night"), "entry-1")
    runtime._async_turn_off_controlled_entities = AsyncMock()

    gate = asyncio.Event()

    async def blocking_sleep(_seconds: int) -> None:
        await gate.wait()

    monkeypatch.setattr("custom_components.switch_manager.controller.asyncio.sleep", blocking_sleep)

    await runtime._async_restart_timer()
    assert runtime._timer_task is not None

    await runtime._async_cancel_timer()
    assert runtime._timer_task is None

    async def immediate_sleep(_seconds: int) -> None:
        return None

    monkeypatch.setattr("custom_components.switch_manager.controller.asyncio.sleep", immediate_sleep)
    runtime._timer_task = object()
    runtime._async_all_detectors_are_clear = AsyncMock(return_value=True)
    await runtime._async_timer_worker()
    assert runtime._timer_task is None
    runtime._async_turn_off_controlled_entities.assert_awaited_once()

    runtime._async_turn_off_entity = AsyncMock()
    runtime._async_turn_off_controlled_entities = (
        ControllerRuntime._async_turn_off_controlled_entities.__get__(
            runtime,
            ControllerRuntime,
        )
    )
    await runtime._async_turn_off_controlled_entities()
    assert runtime._async_turn_off_entity.await_args_list[-2].args[0] == "light.hallway"
    assert runtime._async_turn_off_entity.await_args_list[-1].args[0] == "light.night"


@pytest.mark.asyncio
async def test_timer_worker_restarts_when_detector_still_active(hass, monkeypatch) -> None:
    """Timer expiry should restart instead of turning off while detection remains active."""

    runtime = ControllerRuntime(
        hass,
        GlobalConfig(),
        _controller(detector_sensor_1="binary_sensor.motion1"),
        "entry-1",
    )
    runtime._async_turn_off_controlled_entities = AsyncMock()
    runtime._async_restart_timer = AsyncMock()
    runtime._async_all_detectors_are_clear = AsyncMock(return_value=False)

    async def immediate_sleep(_seconds: int) -> None:
        return None

    monkeypatch.setattr("custom_components.switch_manager.controller.asyncio.sleep", immediate_sleep)
    runtime._timer_task = object()

    await runtime._async_timer_worker()

    runtime._async_restart_timer.assert_awaited_once()
    runtime._async_turn_off_controlled_entities.assert_not_awaited()
    assert runtime._timer_task is None


@pytest.mark.asyncio
async def test_entity_helpers_cover_service_calls_and_detector_state_checks(hass, monkeypatch) -> None:
    """State and entity helper methods should cover warnings, clearing, and filtering."""

    controller = _controller(
        night_entity="light.night",
        detector_sensor_1="binary_sensor.motion1",
        detector_sensor_2="binary_sensor.motion2",
        illuminance_sensor="sensor.lux",
        illuminance_threshold_entity="input_number.threshold",
        turn_off_entity_1="switch.a",
        turn_off_entity_2="switch.b",
    )
    runtime = ControllerRuntime(
        hass,
        GlobalConfig.from_mapping(
            {
                "smart_mode_entity": "binary_sensor.smart",
                "night_mode_entity": "binary_sensor.night_mode",
                "alarm_entity": "alarm_control_panel.house",
                "alarm_timer_entity": "timer.house",
                "alarm_notification_script_entity": "script.notify",
            }
        ),
        controller,
        "entry-1",
    )

    report_issue = Mock()
    clear_issue = Mock()
    monkeypatch.setattr("custom_components.switch_manager.controller.report_configured_entity_unavailable", report_issue)
    monkeypatch.setattr("custom_components.switch_manager.controller.clear_configured_entity_issue", clear_issue)

    hass.states.async_set("binary_sensor.motion1", "off")
    hass.states.async_set("binary_sensor.motion2", "on")
    hass.states.async_set("sensor.lux", "not-a-number")
    hass.states.async_set("input_number.threshold", "15")
    hass.states.async_set("binary_sensor.smart", "unknown")

    assert runtime._configured_listener_entities() == ["light.night", "binary_sensor.motion1", "binary_sensor.motion2"]
    assert await runtime._async_all_detectors_are_clear() is False
    hass.states.async_set("binary_sensor.motion2", "off")
    assert await runtime._async_all_detectors_are_clear() is True
    assert runtime._first_active_detector() is None
    hass.states.async_set("binary_sensor.motion1", "on")
    assert runtime._first_active_detector() == "binary_sensor.motion1"
    assert runtime._state_as_float(State("sensor.lux", "5.5")) == 5.5
    assert runtime._state_as_float(State("sensor.lux", "bad")) is None

    assert runtime._get_state("binary_sensor.smart", "smart_mode_entity") is None
    assert report_issue.call_count == 1
    hass.states.async_set("binary_sensor.smart", "on")
    assert runtime._get_state("binary_sensor.smart", "smart_mode_entity") is not None
    clear_issue.assert_called_once()

    checks = runtime._entity_checks()
    assert ("turn_off_entity_2", "switch.b") in checks
    runtime._unavailable_entities.add(("smart_mode_entity", "binary_sensor.smart"))
    runtime._clear_all_entity_issues()
    assert runtime._unavailable_entities == set()