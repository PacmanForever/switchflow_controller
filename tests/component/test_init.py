"""Component tests for integration setup and unload."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from custom_components.switch_manager import (
    _async_migrate_legacy_storage_to_subentries,
    _async_update_listener,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.switch_manager.const import DATA_MANAGER, DOMAIN
from custom_components.switch_manager.models import ControllerConfig
from pytest_homeassistant_custom_component.common import MockConfigEntry


@pytest.mark.asyncio
async def test_async_setup_entry_registers_manager_and_services(hass, monkeypatch) -> None:
    """Setup should create a manager, store it, and register services."""

    manager = SimpleNamespace(async_setup=AsyncMock())
    manager_factory = Mock(return_value=manager)
    setup_services = AsyncMock()
    config_entry = SimpleNamespace(
        entry_id="entry-1",
        add_update_listener=Mock(return_value=lambda: None),
        async_on_unload=Mock(),
    )

    monkeypatch.setattr(
        "custom_components.switch_manager.SwitchManagerRuntime", manager_factory
    )
    monkeypatch.setattr(
        "custom_components.switch_manager.async_setup_services", setup_services
    )
    monkeypatch.setattr(
        "custom_components.switch_manager._async_migrate_legacy_storage_to_subentries",
        AsyncMock(),
    )

    result = await async_setup_entry(hass, config_entry)

    assert result is True
    manager_factory.assert_called_once_with(hass, config_entry)
    manager.async_setup.assert_awaited_once()
    assert hass.data[DOMAIN]["entry-1"][DATA_MANAGER] is manager
    setup_services.assert_awaited_once_with(hass)
    config_entry.add_update_listener.assert_called_once()
    config_entry.async_on_unload.assert_called_once()


@pytest.mark.asyncio
async def test_async_setup_entry_migrates_legacy_storage_to_subentries(hass, monkeypatch) -> None:
    """Legacy storage-backed controllers should move into config subentries on setup."""

    manager = SimpleNamespace(async_setup=AsyncMock())
    manager_factory = Mock(return_value=manager)
    setup_services = AsyncMock()
    config_entry = MockConfigEntry(domain=DOMAIN, title="Switch Manager", data={})
    config_entry.add_to_hass(hass)
    controller = ControllerConfig.from_mapping(
        {
            "id": "hallway",
            "name": "Hallway",
            "main_entity": "light.hallway",
            "wait_time": 120,
        }
    )

    monkeypatch.setattr(
        "custom_components.switch_manager.SwitchManagerRuntime", manager_factory
    )
    monkeypatch.setattr(
        "custom_components.switch_manager.async_setup_services", setup_services
    )
    monkeypatch.setattr(
        "custom_components.switch_manager.SwitchManagerStorage.async_load",
        AsyncMock(return_value=[controller]),
    )
    monkeypatch.setattr(
        "custom_components.switch_manager.SwitchManagerStorage.async_clear",
        AsyncMock(),
    )

    result = await async_setup_entry(hass, config_entry)

    assert result is True
    subentry = next(iter(config_entry.subentries.values()))
    assert subentry.unique_id == "hallway"
    assert subentry.title == "Hallway"
    assert subentry.data["main_entity"] == "light.hallway"


@pytest.mark.asyncio
async def test_async_unload_entry_unloads_last_manager_and_services(hass, monkeypatch) -> None:
    """Unloading the last entry should also unload services."""

    unload_services = AsyncMock()
    manager = SimpleNamespace(async_unload=AsyncMock())
    config_entry = SimpleNamespace(entry_id="entry-1")
    hass.data[DOMAIN] = {"entry-1": {DATA_MANAGER: manager}}

    monkeypatch.setattr(
        "custom_components.switch_manager.async_unload_services", unload_services
    )

    result = await async_unload_entry(hass, config_entry)

    assert result is True
    manager.async_unload.assert_awaited_once()
    unload_services.assert_awaited_once_with(hass)
    assert DOMAIN not in hass.data


@pytest.mark.asyncio
async def test_async_unload_entry_keeps_services_when_other_entries_exist(
    hass, monkeypatch
) -> None:
    """Unloading one entry should keep services when another entry remains."""

    unload_services = AsyncMock()
    manager = SimpleNamespace(async_unload=AsyncMock())
    config_entry = SimpleNamespace(entry_id="entry-1")
    hass.data[DOMAIN] = {
        "entry-1": {DATA_MANAGER: manager},
        "entry-2": {DATA_MANAGER: object()},
    }

    monkeypatch.setattr(
        "custom_components.switch_manager.async_unload_services", unload_services
    )

    result = await async_unload_entry(hass, config_entry)

    assert result is True
    manager.async_unload.assert_awaited_once()
    unload_services.assert_not_awaited()
    assert DOMAIN in hass.data
    assert "entry-2" in hass.data[DOMAIN]


@pytest.mark.asyncio
async def test_update_listener_reloads_runtime_manager(hass) -> None:
    """Config-entry updates should reload the stored manager."""

    manager = SimpleNamespace(async_reload=AsyncMock())
    config_entry = SimpleNamespace(entry_id="entry-1")
    hass.data[DOMAIN] = {"entry-1": {DATA_MANAGER: manager}}

    await _async_update_listener(hass, config_entry)

    manager.async_reload.assert_awaited_once()


@pytest.mark.asyncio
async def test_legacy_storage_migration_skips_when_subentries_exist(hass, monkeypatch) -> None:
    """Migration should not run when the entry already has controller subentries."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Switch Manager",
        data={},
        subentries_data=[
            {
                "subentry_id": "sub-1",
                "subentry_type": "controller",
                "title": "Hallway",
                "unique_id": "hallway",
                "data": {"main_entity": "light.hallway", "wait_time": 120, "enabled": True},
            }
        ],
    )
    config_entry.add_to_hass(hass)
    load_mock = AsyncMock()
    monkeypatch.setattr(
        "custom_components.switch_manager.SwitchManagerStorage.async_load",
        load_mock,
    )

    await _async_migrate_legacy_storage_to_subentries(hass, config_entry)

    load_mock.assert_not_awaited()