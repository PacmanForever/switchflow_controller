"""Domain models for the SwitchFlow Controller integration."""

from __future__ import annotations

from datetime import timedelta
from dataclasses import dataclass
from typing import Any

from .const import (
    CONF_ACTIVATE_ON_DETECTION,
    CONF_ALARM_ENTITY,
    CONF_ALARM_NOTIFICATION_SCRIPT_ENTITY,
    CONF_ALARM_TIMER_ENTITY,
    CONF_AREA_ID,
    CONF_CONTROLLER_ID,
    CONF_DETECTOR_SENSOR_1,
    CONF_DETECTOR_SENSOR_2,
    CONF_ENABLED,
    CONF_ILLUMINANCE_SENSOR,
    CONF_ILLUMINANCE_THRESHOLD_LUX,
    CONF_ILLUMINANCE_THRESHOLD_ENTITY,
    CONF_MAIN_ENTITY,
    CONF_NIGHT_ENTITY,
    CONF_NIGHT_MODE_ENTITY,
    CONF_NOTIFY_WITH_ALARM,
    CONF_OPENING_ALARM_LIGHT_DURATION,
    CONF_OPENING_SENSOR_1,
    CONF_OPENING_SENSOR_2,
    CONF_SMART_MODE_ENTITY,
    CONF_TURN_OFF_ENTITY_1,
    CONF_TURN_OFF_ENTITY_2,
    CONF_TURN_OFF_WHEN_PRESENCE_CLEARS,
    CONF_USE_NIGHT_ENTITY_NAME,
    CONF_WAIT_TIME,
    DEFAULT_OPENING_ALARM_LIGHT_DURATION_SECONDS,
    DEFAULT_WAIT_TIME_SECONDS,
)


def _normalize_entity_id(value: Any) -> str | None:
    """Normalize optional entity identifiers."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"Expected string entity id, got {type(value)!r}")
    cleaned = value.strip()
    return cleaned or None


def _normalize_bool(value: Any, *, default: bool) -> bool:
    """Normalize optional boolean values."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    raise ValueError(f"Expected boolean value, got {type(value)!r}")


def _normalize_wait_time(value: Any) -> int:
    """Normalize the controller safety wait time."""
    if value is None:
        raise ValueError("wait_time is required")
    if isinstance(value, timedelta):
        wait_time = int(value.total_seconds())
    elif isinstance(value, dict):
        units = {
            "days": 86400,
            "hours": 3600,
            "minutes": 60,
            "seconds": 1,
            "milliseconds": 0.001,
        }
        total_seconds = 0.0
        for key, multiplier in units.items():
            unit_value = value.get(key, 0)
            if unit_value:
                total_seconds += float(unit_value) * multiplier
        wait_time = int(total_seconds)
    else:
        wait_time = int(value)
    if wait_time <= 0:
        raise ValueError("wait_time must be a positive integer")
    return wait_time


def _normalize_optional_float(value: Any) -> float | None:
    """Normalize optional numeric values."""
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        return float(cleaned)
    if isinstance(value, int | float):
        return float(value)
    raise ValueError(f"Expected numeric value, got {type(value)!r}")


@dataclass(slots=True)
class GlobalConfig:
    """Shared global configuration for the integration."""

    smart_mode_entity: str | None = None
    night_mode_entity: str | None = None
    alarm_entity: str | None = None
    alarm_timer_entity: str | None = None
    alarm_notification_script_entity: str | None = None
    opening_alarm_light_duration: int = DEFAULT_OPENING_ALARM_LIGHT_DURATION_SECONDS

    @classmethod
    def from_mapping(cls, data: dict[str, Any] | None) -> "GlobalConfig":
        """Create a global config from config-entry data or options."""
        source = data or {}
        return cls(
            smart_mode_entity=_normalize_entity_id(source.get(CONF_SMART_MODE_ENTITY)),
            night_mode_entity=_normalize_entity_id(source.get(CONF_NIGHT_MODE_ENTITY)),
            alarm_entity=_normalize_entity_id(source.get(CONF_ALARM_ENTITY)),
            alarm_timer_entity=_normalize_entity_id(source.get(CONF_ALARM_TIMER_ENTITY)),
            alarm_notification_script_entity=_normalize_entity_id(
                source.get(CONF_ALARM_NOTIFICATION_SCRIPT_ENTITY)
            ),
            opening_alarm_light_duration=_normalize_wait_time(
                source.get(
                    CONF_OPENING_ALARM_LIGHT_DURATION,
                    DEFAULT_OPENING_ALARM_LIGHT_DURATION_SECONDS,
                )
            ),
        )

    def as_dict(self) -> dict[str, str]:
        """Return a dict suitable for config-entry storage."""
        result: dict[str, str] = {}
        if self.smart_mode_entity:
            result[CONF_SMART_MODE_ENTITY] = self.smart_mode_entity
        if self.night_mode_entity:
            result[CONF_NIGHT_MODE_ENTITY] = self.night_mode_entity
        if self.alarm_entity:
            result[CONF_ALARM_ENTITY] = self.alarm_entity
        if self.alarm_timer_entity:
            result[CONF_ALARM_TIMER_ENTITY] = self.alarm_timer_entity
        if self.alarm_notification_script_entity:
            result[CONF_ALARM_NOTIFICATION_SCRIPT_ENTITY] = (
                self.alarm_notification_script_entity
            )
        if self.opening_alarm_light_duration != DEFAULT_OPENING_ALARM_LIGHT_DURATION_SECONDS:
            result[CONF_OPENING_ALARM_LIGHT_DURATION] = self.opening_alarm_light_duration
        return result


@dataclass(slots=True)
class ControllerConfig:
    """Persistent per-controller configuration."""

    controller_id: str
    name: str
    enabled: bool
    main_entity: str
    wait_time: int
    night_entity: str | None = None
    detector_sensor_1: str | None = None
    detector_sensor_2: str | None = None
    opening_sensor_1: str | None = None
    opening_sensor_2: str | None = None
    illuminance_sensor: str | None = None
    illuminance_threshold_lux: float | None = None
    illuminance_threshold_entity: str | None = None
    turn_off_when_presence_clears: bool = False
    activate_on_detection: bool = False
    notify_with_alarm: bool = False
    use_night_entity_name: bool = False
    turn_off_entity_1: str | None = None
    turn_off_entity_2: str | None = None
    area_id: str | None = None

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "ControllerConfig":
        """Create a validated controller configuration from storage data."""
        controller_id = str(data.get(CONF_CONTROLLER_ID, "")).strip()
        name = str(data.get("name", "")).strip()
        main_entity = _normalize_entity_id(data.get(CONF_MAIN_ENTITY))

        if not controller_id:
            raise ValueError("controller id is required")
        if not name:
            raise ValueError("controller name is required")
        if not main_entity:
            raise ValueError("main_entity is required")

        return cls(
            controller_id=controller_id,
            name=name,
            enabled=_normalize_bool(data.get(CONF_ENABLED), default=True),
            main_entity=main_entity,
            wait_time=_normalize_wait_time(data.get(CONF_WAIT_TIME)),
            night_entity=_normalize_entity_id(data.get(CONF_NIGHT_ENTITY)),
            detector_sensor_1=_normalize_entity_id(data.get(CONF_DETECTOR_SENSOR_1)),
            detector_sensor_2=_normalize_entity_id(data.get(CONF_DETECTOR_SENSOR_2)),
            opening_sensor_1=_normalize_entity_id(data.get(CONF_OPENING_SENSOR_1)),
            opening_sensor_2=_normalize_entity_id(data.get(CONF_OPENING_SENSOR_2)),
            illuminance_sensor=_normalize_entity_id(data.get(CONF_ILLUMINANCE_SENSOR)),
            illuminance_threshold_lux=_normalize_optional_float(
                data.get(CONF_ILLUMINANCE_THRESHOLD_LUX)
            ),
            illuminance_threshold_entity=_normalize_entity_id(
                data.get(CONF_ILLUMINANCE_THRESHOLD_ENTITY)
            ),
            turn_off_when_presence_clears=_normalize_bool(
                data.get(CONF_TURN_OFF_WHEN_PRESENCE_CLEARS), default=False
            ),
            activate_on_detection=_normalize_bool(
                data.get(CONF_ACTIVATE_ON_DETECTION), default=False
            ),
            notify_with_alarm=_normalize_bool(
                data.get(CONF_NOTIFY_WITH_ALARM), default=False
            ),
            use_night_entity_name=_normalize_bool(
                data.get(CONF_USE_NIGHT_ENTITY_NAME), default=False
            ),
            turn_off_entity_1=_normalize_entity_id(data.get(CONF_TURN_OFF_ENTITY_1)),
            turn_off_entity_2=_normalize_entity_id(data.get(CONF_TURN_OFF_ENTITY_2)),
            area_id=_normalize_entity_id(data.get(CONF_AREA_ID)),
        )

    def as_dict(self) -> dict[str, Any]:
        """Serialize the controller configuration for storage."""
        return {
            CONF_CONTROLLER_ID: self.controller_id,
            "name": self.name,
            CONF_ENABLED: self.enabled,
            CONF_MAIN_ENTITY: self.main_entity,
            CONF_NIGHT_ENTITY: self.night_entity,
            CONF_DETECTOR_SENSOR_1: self.detector_sensor_1,
            CONF_DETECTOR_SENSOR_2: self.detector_sensor_2,
            CONF_OPENING_SENSOR_1: self.opening_sensor_1,
            CONF_OPENING_SENSOR_2: self.opening_sensor_2,
            CONF_ILLUMINANCE_SENSOR: self.illuminance_sensor,
            CONF_ILLUMINANCE_THRESHOLD_LUX: self.illuminance_threshold_lux,
            CONF_ILLUMINANCE_THRESHOLD_ENTITY: self.illuminance_threshold_entity,
            CONF_WAIT_TIME: self.wait_time,
            CONF_TURN_OFF_WHEN_PRESENCE_CLEARS: self.turn_off_when_presence_clears,
            CONF_ACTIVATE_ON_DETECTION: self.activate_on_detection,
            CONF_NOTIFY_WITH_ALARM: self.notify_with_alarm,
            CONF_USE_NIGHT_ENTITY_NAME: self.use_night_entity_name,
            CONF_TURN_OFF_ENTITY_1: self.turn_off_entity_1,
            CONF_TURN_OFF_ENTITY_2: self.turn_off_entity_2,
            CONF_AREA_ID: self.area_id,
        }


def default_controller_payload(*, controller_id: str, name: str, main_entity: str) -> dict[str, Any]:
    """Create a default payload for a new controller."""
    return ControllerConfig(
        controller_id=controller_id,
        name=name,
        enabled=True,
        main_entity=main_entity,
        wait_time=DEFAULT_WAIT_TIME_SECONDS,
    ).as_dict()