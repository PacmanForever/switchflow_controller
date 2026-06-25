"""Controller runtime logic for the SwitchFlow Controller integration."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import logging
import time

from homeassistant.const import (
    STATE_IDLE,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import CoreState, Event, HomeAssistant, State, callback
from homeassistant.helpers.event import EventStateChangedData, async_track_state_change_event

from .const import (
    CONF_ALARM_ENTITY,
    CONF_ALARM_NOTIFICATION_SCRIPT_ENTITY,
    CONF_ALARM_TIMER_ENTITY,
    CONF_DETECTOR_SENSOR_1,
    CONF_DETECTOR_SENSOR_2,
    CONF_ILLUMINANCE_SENSOR,
    CONF_ILLUMINANCE_THRESHOLD_ENTITY,
    CONF_MAIN_ENTITY,
    CONF_NIGHT_ENTITY,
    CONF_NIGHT_MODE_ENTITY,
    CONF_SMART_MODE_ENTITY,
    CONF_TURN_OFF_ENTITY_1,
    CONF_TURN_OFF_ENTITY_2,
    DEFAULT_ILLUMINANCE_THRESHOLD,
)
from .issues import clear_configured_entity_issue, report_configured_entity_unavailable
from .models import ControllerConfig, GlobalConfig

LOGGER = logging.getLogger(__name__)
ARMED_ALARM_STATES = {
    "armed_away",
    "armed_custom_bypass",
    "armed_home",
    "armed_night",
    "armed_vacation",
}
UNAVAILABLE_ISSUE_SUPPRESSED_FIELDS = {
    CONF_NIGHT_ENTITY,
}
STARTUP_UNAVAILABLE_WARNING_GRACE_PERIOD = 30.0


class ControllerRuntime:
    """Explicit runtime container for a single controller."""

    def __init__(
        self,
        hass: HomeAssistant,
        global_config: GlobalConfig,
        controller: ControllerConfig,
        config_entry_id: str,
    ) -> None:
        """Initialize a controller runtime."""
        self.hass = hass
        self.global_config = global_config
        self.controller = controller
        self.config_entry_id = config_entry_id
        self._timer_lock = asyncio.Lock()
        self._timer_task: asyncio.Task[None] | None = None
        self._unsubscribers: list[Callable[[], None]] = []
        self._unavailable_entities: set[tuple[str, str]] = set()
        self._startup_warning_grace_deadline: float | None = None

    async def async_start(self) -> None:
        """Start runtime handling for this controller."""
        LOGGER.debug("Starting controller runtime for %s", self.controller.controller_id)
        self._clear_known_configured_entity_issues()
        if self.hass.state is not CoreState.running:
            self._startup_warning_grace_deadline = (
                time.monotonic() + STARTUP_UNAVAILABLE_WARNING_GRACE_PERIOD
            )

        self.add_unsubscriber(
            async_track_state_change_event(
                self.hass,
                [self.controller.main_entity],
                self._async_handle_main_entity_event,
            )
        )

        for entity_id in self._configured_listener_entities():
            self.add_unsubscriber(
                async_track_state_change_event(
                    self.hass,
                    [entity_id],
                    self._async_handle_optional_entity_event,
                )
            )

        if self._is_smart_mode_enabled() and await self._async_any_controlled_entity_on():
            await self._async_restart_timer()

    async def async_stop(self) -> None:
        """Stop runtime handling for this controller."""
        await self._async_cancel_timer()
        self._clear_all_entity_issues()
        while self._unsubscribers:
            unsubscribe = self._unsubscribers.pop()
            unsubscribe()

    async def async_force_turn_on(self) -> None:
        """Turn on the controller target using the standard fallback path."""
        activated = await self._async_run_detection_activation_path()
        if not activated:
            await self._async_turn_on_entity(self.controller.main_entity)
        await self._async_restart_timer()

    async def async_force_turn_off(self) -> None:
        """Turn off controlled entities and cancel any running timer."""
        await self._async_cancel_timer()
        await self._async_turn_off_controlled_entities()

    async def async_reset_timer(self) -> None:
        """Restart the safety timer when the controller runtime is active."""
        await self._async_restart_timer()

    @callback
    def add_unsubscriber(self, unsubscribe: Callable[[], None]) -> None:
        """Track a runtime cleanup callback."""
        self._unsubscribers.append(unsubscribe)

    @callback
    def _configured_listener_entities(self) -> list[str]:
        """Return the configured optional entities that need listeners."""
        return [
            entity_id
            for entity_id in (
                self.global_config.smart_mode_entity,
                self.controller.night_entity,
                self.controller.detector_sensor_1,
                self.controller.detector_sensor_2,
            )
            if entity_id is not None
        ]

    async def _async_handle_main_entity_event(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Handle main-entity state transitions."""
        new_state = event.data.get("new_state")
        if new_state is None:
            return

        if not self._is_smart_mode_enabled():
            return

        if new_state.state == STATE_ON:
            await self._async_turn_off_configured_entities(
                [self.controller.turn_off_entity_1, self.controller.turn_off_entity_2]
            )
            await self._async_restart_timer()
            return

        if new_state.state == STATE_OFF:
            await self._async_cancel_timer()
            if await self._async_is_entity_on(
                self.controller.night_entity,
                field_name=CONF_NIGHT_ENTITY,
            ):
                await self._async_turn_off_entity(self.controller.night_entity)

    async def _async_handle_optional_entity_event(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Handle state changes for detector and optional night entities."""
        entity_id = event.data["entity_id"]
        new_state = event.data.get("new_state")
        if new_state is None:
            return

        if entity_id == self.global_config.smart_mode_entity:
            await self._async_handle_smart_mode_event(new_state)
            return

        if entity_id in {
            self.controller.detector_sensor_1,
            self.controller.detector_sensor_2,
        }:
            await self._async_handle_detector_state_change(new_state)
            return

        if entity_id != self.controller.night_entity:
            return

        if not self._is_smart_mode_enabled():
            return

        if new_state.state == STATE_ON:
            await self._async_turn_off_configured_entities(
                [self.controller.turn_off_entity_1, self.controller.turn_off_entity_2]
            )
            await self._async_restart_timer()
            return

        if new_state.state != STATE_OFF:
            return

        await self._async_cancel_timer()
        if await self._async_is_entity_on(
            self.controller.main_entity,
            field_name=CONF_MAIN_ENTITY,
        ):
            await self._async_turn_off_entity(self.controller.main_entity)

    async def _async_handle_detector_state_change(self, new_state: State) -> None:
        """Process detector-triggered runtime logic."""
        if new_state.state == STATE_ON:
            if not self._is_smart_mode_enabled():
                LOGGER.debug(
                    "Skipping automation for %s because smart mode is disabled",
                    self.controller.controller_id,
                )
                return

            activated = await self._async_run_alarm_notification_path()
            if self.controller.activate_on_detection:
                activated = await self._async_run_detection_activation_path() or activated

            if activated or await self._async_any_controlled_entity_on():
                await self._async_restart_timer()
            return

        if (
            self.controller.turn_off_when_presence_clears
            and await self._async_all_detectors_are_clear()
        ):
            await self._async_turn_off_controlled_entities()
            await self._async_cancel_timer()

    async def _async_handle_smart_mode_event(self, new_state: State) -> None:
        """Stop automation timing when smart mode is disabled."""
        if new_state.state != STATE_ON:
            await self._async_cancel_timer()

    def _is_smart_mode_enabled(self) -> bool:
        """Return whether automation is allowed to run."""
        if self.global_config.smart_mode_entity is None:
            return True

        state = self._get_state(self.global_config.smart_mode_entity, CONF_SMART_MODE_ENTITY)
        if state is None:
            return False
        return state.state == STATE_ON

    async def _async_run_alarm_notification_path(self) -> bool:
        """Run the alarm notification branch if configured and eligible."""
        if not self.controller.notify_with_alarm:
            return False
        if self.global_config.alarm_entity is None:
            return False

        alarm_state = self._get_state(self.global_config.alarm_entity, CONF_ALARM_ENTITY)
        if alarm_state is None or alarm_state.state not in ARMED_ALARM_STATES:
            return False

        if self.global_config.alarm_timer_entity is not None:
            timer_state = self._get_state(
                self.global_config.alarm_timer_entity,
                CONF_ALARM_TIMER_ENTITY,
            )
            if timer_state is not None and timer_state.state != STATE_IDLE:
                return False

        await self._async_turn_on_entity(self.controller.main_entity)

        if self.global_config.alarm_notification_script_entity is not None:
            script_state = self._get_state(
                self.global_config.alarm_notification_script_entity,
                CONF_ALARM_NOTIFICATION_SCRIPT_ENTITY,
            )
            if script_state is None:
                return True

            await self.hass.services.async_call(
                "script",
                self.global_config.alarm_notification_script_entity.split(".", 1)[1],
                {
                    "message": (
                        f"SwitchFlow Controller alarm notification from {self.controller.name}"
                    ),
                    "controller_name": self.controller.name,
                    "trigger_entity_id": self._first_active_detector(),
                },
                blocking=True,
            )

        return True

    async def _async_run_detection_activation_path(self) -> bool:
        """Run the normal detection activation path."""
        if self._is_night_mode_active():
            if not await self._async_is_entity_on(
                self.controller.main_entity,
                field_name=CONF_MAIN_ENTITY,
            ):
                if self.controller.night_entity and not await self._async_is_entity_on(
                    self.controller.night_entity,
                    field_name=CONF_NIGHT_ENTITY,
                ):
                    await self._async_turn_on_entity(self.controller.night_entity)
                    return True

                await self._async_turn_on_entity(self.controller.main_entity)
                return True

        illuminance_result = await self._async_evaluate_illuminance_rule()
        if illuminance_result is True:
            if not await self._async_is_entity_on(
                self.controller.main_entity,
                field_name=CONF_MAIN_ENTITY,
            ):
                await self._async_turn_on_entity(self.controller.main_entity)
            return True
        if illuminance_result is False:
            return await self._async_is_entity_on(
                self.controller.main_entity,
                field_name=CONF_MAIN_ENTITY,
            ) or await self._async_is_entity_on(
                self.controller.night_entity,
                field_name=CONF_NIGHT_ENTITY,
            )

        if not await self._async_is_entity_on(
            self.controller.main_entity,
            field_name=CONF_MAIN_ENTITY,
        ):
            await self._async_turn_on_entity(self.controller.main_entity)
            return True

        return await self._async_is_entity_on(
            self.controller.main_entity,
            field_name=CONF_MAIN_ENTITY,
        ) or await self._async_is_entity_on(
            self.controller.night_entity,
            field_name=CONF_NIGHT_ENTITY,
        )

    def _is_night_mode_active(self) -> bool:
        """Return whether global night mode is active."""
        if self.global_config.night_mode_entity is None:
            return False
        state = self._get_state(self.global_config.night_mode_entity, CONF_NIGHT_MODE_ENTITY)
        return state is not None and state.state == STATE_ON

    async def _async_evaluate_illuminance_rule(self) -> bool | None:
        """Evaluate illuminance gating.

        Returns `True` when illuminance allows activation, `False` when it
        explicitly blocks activation for this cycle, and `None` when the rule
        should fall back to the standard activation path.
        """
        if self.controller.illuminance_sensor is None:
            return None

        lux_state = self._get_state(
            self.controller.illuminance_sensor,
            CONF_ILLUMINANCE_SENSOR,
        )
        lux_value = self._state_as_float(lux_state)
        if lux_value is None:
            return None

        threshold = DEFAULT_ILLUMINANCE_THRESHOLD
        if self.controller.illuminance_threshold_entity is not None:
            threshold_state = self._get_state(
                self.controller.illuminance_threshold_entity,
                CONF_ILLUMINANCE_THRESHOLD_ENTITY,
            )
            configured_threshold = self._state_as_float(threshold_state)
            if configured_threshold is not None:
                threshold = configured_threshold

        return lux_value < threshold

    async def _async_restart_timer(self) -> None:
        """Restart the safety timer for this controller."""
        async with self._timer_lock:
            await self._async_cancel_timer_locked()
            self._timer_task = self.hass.async_create_task(self._async_timer_worker())

    async def _async_cancel_timer(self) -> None:
        """Cancel the active safety timer if present."""
        async with self._timer_lock:
            await self._async_cancel_timer_locked()

    async def _async_cancel_timer_locked(self) -> None:
        """Cancel the active safety timer while holding the timer lock."""
        if self._timer_task is None:
            return

        self._timer_task.cancel()
        try:
            await self._timer_task
        except asyncio.CancelledError:
            pass
        self._timer_task = None

    async def _async_timer_worker(self) -> None:
        """Wait for the controller timeout and then shut down controlled entities."""
        try:
            while True:
                await asyncio.sleep(self.controller.wait_time)
                if await self._async_all_detectors_are_clear():
                    await self._async_turn_off_controlled_entities()
                    return
        except asyncio.CancelledError:
            raise
        finally:
            self._timer_task = None

    async def _async_any_controlled_entity_on(self) -> bool:
        """Return whether the main or night entity is currently on."""
        return self._is_entity_on_silently(self.controller.main_entity) or self._is_entity_on_silently(
            self.controller.night_entity
        )

    def _is_entity_on_silently(self, entity_id: str | None) -> bool:
        """Return whether an entity is on without creating availability issues."""
        if entity_id is None:
            return False
        state = self.hass.states.get(entity_id)
        return state is not None and state.state == STATE_ON

    async def _async_turn_off_controlled_entities(self) -> None:
        """Turn off the main and night entities if they are on."""
        await self._async_turn_off_entity(self.controller.main_entity)
        if self.controller.night_entity is not None:
            await self._async_turn_off_entity(self.controller.night_entity)

    async def _async_turn_off_configured_entities(
        self, entity_ids: list[str | None]
    ) -> None:
        """Turn off configured secondary entities."""
        for entity_id in entity_ids:
            if entity_id is not None:
                await self._async_turn_off_entity(entity_id)

    async def _async_turn_on_entity(self, entity_id: str | None) -> None:
        """Turn on an entity when it is configured."""
        if entity_id is None:
            return

        await self.hass.services.async_call(
            entity_id.split(".", 1)[0],
            "turn_on",
            {"entity_id": entity_id},
            blocking=True,
        )

    async def _async_turn_off_entity(self, entity_id: str | None) -> None:
        """Turn off an entity when it is configured."""
        if entity_id is None:
            return

        await self.hass.services.async_call(
            entity_id.split(".", 1)[0],
            "turn_off",
            {"entity_id": entity_id},
            blocking=True,
        )

    async def _async_is_entity_on(
        self,
        entity_id: str | None,
        *,
        field_name: str,
    ) -> bool:
        """Return whether an entity exists and is currently on."""
        if entity_id is None:
            return False
        state = self._get_state(entity_id, field_name)
        return state is not None and state.state == STATE_ON

    def _get_state(self, entity_id: str, field_name: str) -> State | None:
        """Read an entity state and warn once when a configured entity is unavailable."""
        state = self.hass.states.get(entity_id)
        issue_key = (field_name, entity_id)
        if state is None or state.state in {STATE_UNAVAILABLE, STATE_UNKNOWN}:
            if self.hass.state is not CoreState.running:
                return None
            if (
                self._startup_warning_grace_deadline is not None
                and time.monotonic() < self._startup_warning_grace_deadline
            ):
                return None
            if field_name in UNAVAILABLE_ISSUE_SUPPRESSED_FIELDS:
                return None
            if issue_key not in self._unavailable_entities:
                LOGGER.warning(
                    "Configured entity %s for controller %s field %s is unavailable; falling back when possible",
                    entity_id,
                    self.controller.controller_id,
                    field_name,
                )
                report_configured_entity_unavailable(
                    self.hass,
                    entry_id=self.config_entry_id,
                    controller_id=self.controller.controller_id,
                    controller_name=self.controller.name,
                    field_name=field_name,
                    entity_id=entity_id,
                )
                self._unavailable_entities.add(issue_key)
            return None

        if issue_key in self._unavailable_entities:
            clear_configured_entity_issue(
                self.hass,
                controller_id=self.controller.controller_id,
                field_name=field_name,
                entity_id=entity_id,
            )
            self._unavailable_entities.remove(issue_key)
        return state

    async def _async_all_detectors_are_clear(self) -> bool:
        """Return whether every configured detector is currently clear."""
        detector_ids = [
            entity_id
            for entity_id in (
                self.controller.detector_sensor_1,
                self.controller.detector_sensor_2,
            )
            if entity_id is not None
        ]
        if not detector_ids:
            return True

        for entity_id in detector_ids:
            field_name = (
                CONF_DETECTOR_SENSOR_1
                if entity_id == self.controller.detector_sensor_1
                else CONF_DETECTOR_SENSOR_2
            )
            state = self._get_state(entity_id, field_name)
            if state is not None and state.state == STATE_ON:
                return False
        return True

    def _first_active_detector(self) -> str | None:
        """Return the first currently active detector entity id."""
        for entity_id in (
            self.controller.detector_sensor_1,
            self.controller.detector_sensor_2,
        ):
            if entity_id is None:
                continue
            state = self.hass.states.get(entity_id)
            if state is not None and state.state == STATE_ON:
                return entity_id
        return None

    @staticmethod
    def _state_as_float(state: State | None) -> float | None:
        """Convert a numeric state to float when possible."""
        if state is None:
            return None
        try:
            return float(state.state)
        except (TypeError, ValueError):
            return None

    @callback
    def _entity_checks(self) -> list[tuple[str, str]]:
        """Return configured entities that should be checked for availability."""
        entity_checks: list[tuple[str, str | None]] = [
            (CONF_SMART_MODE_ENTITY, self.global_config.smart_mode_entity),
            (CONF_NIGHT_MODE_ENTITY, self.global_config.night_mode_entity),
            (CONF_ALARM_ENTITY, self.global_config.alarm_entity),
            (CONF_ALARM_TIMER_ENTITY, self.global_config.alarm_timer_entity),
            (
                CONF_ALARM_NOTIFICATION_SCRIPT_ENTITY,
                self.global_config.alarm_notification_script_entity,
            ),
            (CONF_NIGHT_ENTITY, self.controller.night_entity),
            (CONF_DETECTOR_SENSOR_1, self.controller.detector_sensor_1),
            (CONF_DETECTOR_SENSOR_2, self.controller.detector_sensor_2),
            (CONF_ILLUMINANCE_SENSOR, self.controller.illuminance_sensor),
            (
                CONF_ILLUMINANCE_THRESHOLD_ENTITY,
                self.controller.illuminance_threshold_entity,
            ),
            (CONF_TURN_OFF_ENTITY_1, self.controller.turn_off_entity_1),
            (CONF_TURN_OFF_ENTITY_2, self.controller.turn_off_entity_2),
        ]
        return [
            (field_name, entity_id)
            for field_name, entity_id in entity_checks
            if entity_id is not None
        ]

    @callback
    def _clear_all_entity_issues(self) -> None:
        """Clear transient issues when stopping the runtime."""
        for field_name, entity_id in list(self._unavailable_entities):
            clear_configured_entity_issue(
                self.hass,
                controller_id=self.controller.controller_id,
                field_name=field_name,
                entity_id=entity_id,
            )
        self._unavailable_entities.clear()

    @callback
    def _clear_known_configured_entity_issues(self) -> None:
        """Clear stale issues for currently configured entities on startup.

        This prevents false positives created during earlier startup phases from
        lingering after the runtime is reloaded.
        """
        for field_name, entity_id in self._entity_checks():
            clear_configured_entity_issue(
                self.hass,
                controller_id=self.controller.controller_id,
                field_name=field_name,
                entity_id=entity_id,
            )
        self._unavailable_entities.clear()