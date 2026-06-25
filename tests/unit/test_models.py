"""Tests for switchflow_controller domain models."""

from __future__ import annotations

from datetime import timedelta

import pytest

from custom_components.switchflow_controller.const import CONF_MAIN_ENTITY, CONF_WAIT_TIME
from custom_components.switchflow_controller.models import (
    ControllerConfig,
    GlobalConfig,
    _normalize_bool,
    _normalize_entity_id,
    _normalize_wait_time,
    default_controller_payload,
)


def test_global_config_omits_empty_optional_fields() -> None:
    """Empty optional global values should not be persisted."""
    config = GlobalConfig.from_mapping({})
    assert config.as_dict() == {}


def test_controller_config_requires_wait_time() -> None:
    """Controller validation should require wait_time."""
    with pytest.raises(ValueError, match="wait_time"):
        ControllerConfig.from_mapping(
            {
                "id": "bathroom",
                "name": "Bathroom",
                CONF_MAIN_ENTITY: "light.bathroom",
            }
        )


def test_controller_config_normalizes_payload() -> None:
    """Controller payloads should be normalized consistently."""
    controller = ControllerConfig.from_mapping(
        {
            "id": "hallway",
            "name": "Hallway",
            CONF_MAIN_ENTITY: "light.hallway",
            CONF_WAIT_TIME: 120,
        }
    )

    assert controller.main_entity == "light.hallway"
    assert controller.wait_time == 120
    assert controller.activate_on_detection is True


def test_normalizers_cover_invalid_and_empty_values() -> None:
    """Primitive normalizers should reject invalid input and trim empty values."""

    assert _normalize_entity_id(None) is None
    assert _normalize_entity_id("  ") is None
    assert _normalize_entity_id(" light.hallway ") == "light.hallway"
    with pytest.raises(ValueError, match="Expected string entity id"):
        _normalize_entity_id(123)

    assert _normalize_bool(None, default=True) is True
    assert _normalize_bool(False, default=True) is False
    with pytest.raises(ValueError, match="Expected boolean value"):
        _normalize_bool("yes", default=False)

    assert _normalize_wait_time(timedelta(seconds=5)) == 5
    assert _normalize_wait_time("12") == 12
    assert _normalize_wait_time({"hours": 1, "minutes": 2, "seconds": 3}) == 3723
    with pytest.raises(ValueError, match="positive integer"):
        _normalize_wait_time(0)


def test_global_config_and_controller_validations_cover_required_fields() -> None:
    """Model constructors should reject missing required controller fields."""

    config = GlobalConfig.from_mapping(
        {
            "smart_mode_entity": "binary_sensor.smart",
            "night_mode_entity": "binary_sensor.night",
            "alarm_entity": "alarm_control_panel.house",
            "alarm_timer_entity": "timer.house",
            "alarm_notification_script_entity": "script.notify_house",
        }
    )
    assert config.as_dict() == {
        "smart_mode_entity": "binary_sensor.smart",
        "night_mode_entity": "binary_sensor.night",
        "alarm_entity": "alarm_control_panel.house",
        "alarm_timer_entity": "timer.house",
        "alarm_notification_script_entity": "script.notify_house",
    }

    with pytest.raises(ValueError, match="controller id is required"):
        ControllerConfig.from_mapping(
            {
                "name": "Hallway",
                "main_entity": "light.hallway",
                "wait_time": 10,
            }
        )

    with pytest.raises(ValueError, match="controller name is required"):
        ControllerConfig.from_mapping(
            {
                "id": "hallway",
                "main_entity": "light.hallway",
                "wait_time": 10,
            }
        )

    with pytest.raises(ValueError, match="main_entity is required"):
        ControllerConfig.from_mapping(
            {
                "id": "hallway",
                "name": "Hallway",
                "main_entity": " ",
                "wait_time": 10,
            }
        )


def test_default_controller_payload_uses_default_wait_time() -> None:
    """Default controller payloads should be ready for storage."""

    payload = default_controller_payload(
        controller_id="hallway",
        name="Hallway",
        main_entity="light.hallway",
    )

    assert payload["id"] == "hallway"
    assert payload["name"] == "Hallway"
    assert payload["main_entity"] == "light.hallway"
    assert payload["wait_time"] == 120