"""Component tests for switchflow_controller issue registry handling."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from homeassistant.helpers import issue_registry as ir

from custom_components.switchflow_controller.controller import ControllerRuntime
from custom_components.switchflow_controller.issues import (
    _build_issue_id,
    clear_configured_entity_issue,
    report_configured_entity_unavailable,
)
from custom_components.switchflow_controller.models import ControllerConfig, GlobalConfig


@pytest.mark.asyncio
async def test_unavailable_configured_entity_creates_issue(hass) -> None:
    """Configured-but-unavailable runtime dependencies should create a warning issue when used."""
    controller = ControllerConfig.from_mapping(
        {
            "id": "hallway",
            "name": "Hallway",
            "main_entity": "light.hallway",
            "wait_time": 60,
            "detector_sensor_1": "binary_sensor.hallway_motion",
        }
    )
    hass.states.async_set("light.hallway", "off")

    runtime = ControllerRuntime(hass, GlobalConfig(), controller, "entry-1")
    await runtime.async_start()
    runtime._get_state("binary_sensor.hallway_motion", "detector_sensor_1")

    issue_registry = ir.async_get(hass)
    assert any(
        issue.translation_key == "configured_entity_unavailable"
        for issue in issue_registry.issues.values()
    )

    await runtime.async_stop()


@pytest.mark.asyncio
async def test_issue_clears_when_entity_recovers(hass) -> None:
    """Transient issues should disappear once the entity is available again."""
    controller = ControllerConfig.from_mapping(
        {
            "id": "hallway",
            "name": "Hallway",
            "main_entity": "light.hallway",
            "wait_time": 60,
            "detector_sensor_1": "binary_sensor.hallway_motion",
        }
    )
    hass.states.async_set("light.hallway", "off")

    runtime = ControllerRuntime(hass, GlobalConfig(), controller, "entry-1")
    await runtime.async_start()
    runtime._get_state("binary_sensor.hallway_motion", "detector_sensor_1")
    hass.states.async_set("binary_sensor.hallway_motion", "off")
    runtime._get_state("binary_sensor.hallway_motion", "detector_sensor_1")

    issue_registry = ir.async_get(hass)
    assert not issue_registry.issues

    await runtime.async_stop()


@pytest.mark.asyncio
async def test_unavailable_night_entity_does_not_create_issue(hass) -> None:
    """An unavailable optional night entity should fall back silently without a Repairs issue."""
    controller = ControllerConfig.from_mapping(
        {
            "id": "hallway",
            "name": "Hallway",
            "main_entity": "light.hallway",
            "wait_time": 60,
            "night_entity": "light.hallway_night",
        }
    )
    hass.states.async_set("light.hallway", "off")

    runtime = ControllerRuntime(hass, GlobalConfig(), controller, "entry-1")
    await runtime.async_start()

    issue_registry = ir.async_get(hass)
    assert not issue_registry.issues

    await runtime.async_stop()


def test_issue_helpers_build_create_and_delete_issue(monkeypatch, hass) -> None:
    """Issue helper wrappers should delegate stable ids to the registry."""

    create_issue = Mock()
    delete_issue = Mock()
    monkeypatch.setattr("custom_components.switchflow_controller.issues.ir.async_create_issue", create_issue)
    monkeypatch.setattr("custom_components.switchflow_controller.issues.ir.async_delete_issue", delete_issue)

    issue_id = _build_issue_id("entry-1", "night_entity", "light.hallway_night")
    assert issue_id.startswith("configured_entity_unavailable_entry_1")

    report_configured_entity_unavailable(
        hass,
        entry_id="entry-1",
        controller_id="hallway",
        controller_name="Hallway",
        field_name="night_entity",
        entity_id="light.hallway_night",
    )
    clear_configured_entity_issue(
        hass,
        entry_id="entry-1",
        field_name="night_entity",
        entity_id="light.hallway_night",
    )

    create_issue.assert_called_once()
    delete_issue.assert_called_once()


@pytest.mark.asyncio
async def test_shared_unavailable_entity_creates_one_issue_per_entry(hass) -> None:
    """Controllers sharing a global entity should share one Repairs issue."""
    for controller_id in ("hallway", "kitchen", "living_room"):
        report_configured_entity_unavailable(
            hass,
            entry_id="entry-1",
            controller_id=controller_id,
            controller_name=controller_id,
            field_name="alarm_entity",
            entity_id="alarm_control_panel.house",
        )

    issue_registry = ir.async_get(hass)
    matching_issues = [
        issue
        for issue in issue_registry.issues.values()
        if issue.translation_key == "configured_entity_unavailable"
    ]
    assert len(matching_issues) == 1