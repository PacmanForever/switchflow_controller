"""Unit tests for storage persistence helpers."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from custom_components.switch_manager.models import ControllerConfig
from custom_components.switch_manager.storage import SwitchManagerStorage


def _controller(controller_id: str, *, wait_time: int = 60) -> ControllerConfig:
    return ControllerConfig.from_mapping(
        {
            "id": controller_id,
            "name": controller_id.title(),
            "main_entity": f"light.{controller_id}",
            "wait_time": wait_time,
        }
    )


@pytest.mark.asyncio
async def test_async_load_returns_empty_list_when_store_is_empty(hass) -> None:
    """Missing storage payload should yield no controllers."""

    storage = SwitchManagerStorage(hass)
    storage._store.async_load = AsyncMock(return_value=None)

    controllers = await storage.async_load()

    assert controllers == []
    storage._store.async_save.assert_not_called() if hasattr(storage._store.async_save, "assert_not_called") else None


@pytest.mark.asyncio
async def test_async_load_migrates_and_saves_normalized_payload(hass) -> None:
    """Legacy payloads should be normalized and saved back."""

    storage = SwitchManagerStorage(hass)
    storage._store.async_load = AsyncMock(
        return_value=[
            {
                "id": "hallway",
                "name": "Hallway",
                "main_entity": "light.hallway",
                "wait_time": 120,
            }
        ]
    )
    storage._store.async_save = AsyncMock()

    controllers = await storage.async_load()

    assert [controller.controller_id for controller in controllers] == ["hallway"]
    storage._store.async_save.assert_awaited_once()


@pytest.mark.asyncio
async def test_async_load_returns_normalized_controllers(hass) -> None:
    """Valid payloads should deserialize into controller models."""

    storage = SwitchManagerStorage(hass)
    storage._store.async_load = AsyncMock(
        return_value={
            "version": 1,
            "controllers": [
                {
                    "id": "kitchen",
                    "name": "Kitchen",
                    "main_entity": "light.kitchen",
                    "wait_time": 45,
                }
            ],
        }
    )
    storage._store.async_save = AsyncMock()

    controllers = await storage.async_load()

    assert len(controllers) == 1
    assert controllers[0].controller_id == "kitchen"
    assert controllers[0].wait_time == 45
    storage._store.async_save.assert_not_awaited()


@pytest.mark.asyncio
async def test_async_save_persists_serialized_controllers(hass) -> None:
    """Saving should write the current versioned payload shape."""

    storage = SwitchManagerStorage(hass)
    storage._store.async_save = AsyncMock()

    await storage.async_save([_controller("hallway")])

    payload = storage._store.async_save.await_args.args[0]
    assert payload["version"] == 1
    assert payload["controllers"][0]["id"] == "hallway"


@pytest.mark.asyncio
async def test_async_upsert_replaces_existing_controller(hass) -> None:
    """Upsert should replace a controller with the same id."""

    storage = SwitchManagerStorage(hass)
    storage.async_load = AsyncMock(return_value=[_controller("hallway", wait_time=60)])
    storage.async_save = AsyncMock()

    updated = await storage.async_upsert(_controller("hallway", wait_time=90))

    assert len(updated) == 1
    assert updated[0].wait_time == 90
    storage.async_save.assert_awaited_once_with(updated)


@pytest.mark.asyncio
async def test_async_upsert_appends_new_controller(hass) -> None:
    """Upsert should append when the controller id is new."""

    storage = SwitchManagerStorage(hass)
    storage.async_load = AsyncMock(return_value=[_controller("hallway")])
    storage.async_save = AsyncMock()

    updated = await storage.async_upsert(_controller("kitchen"))

    assert [controller.controller_id for controller in updated] == ["hallway", "kitchen"]
    storage.async_save.assert_awaited_once_with(updated)


@pytest.mark.asyncio
async def test_async_delete_removes_matching_controller(hass) -> None:
    """Delete should persist the remaining controller list."""

    storage = SwitchManagerStorage(hass)
    storage.async_load = AsyncMock(return_value=[_controller("hallway"), _controller("kitchen")])
    storage.async_save = AsyncMock()

    updated = await storage.async_delete("hallway")

    assert [controller.controller_id for controller in updated] == ["kitchen"]
    storage.async_save.assert_awaited_once_with(updated)


@pytest.mark.asyncio
async def test_async_clear_persists_empty_controller_list(hass) -> None:
    """Clearing storage should persist an empty controller payload."""

    storage = SwitchManagerStorage(hass)
    storage.async_save = AsyncMock()

    await storage.async_clear()

    storage.async_save.assert_awaited_once_with([])


def test_normalize_payload_replaces_invalid_controller_container() -> None:
    """Invalid controller containers should normalize to an empty list."""

    payload, migrated = SwitchManagerStorage._normalize_payload({"version": 1, "controllers": {}})

    assert migrated is True
    assert payload == {"version": 1, "controllers": []}