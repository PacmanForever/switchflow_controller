"""Storage helpers for Switch Manager controller configuration."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import STORAGE_KEY, STORAGE_VERSION
from .models import ControllerConfig


class SwitchManagerStorage:
    """Versioned storage wrapper for controller configuration records."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the storage helper."""
        self._store = Store[dict[str, Any]](hass, STORAGE_VERSION, STORAGE_KEY)

    async def async_load(self) -> list[ControllerConfig]:
        """Load controller records from storage."""
        payload = await self._store.async_load()
        if not payload:
            return []

        normalized_payload, migrated = self._normalize_payload(payload)
        if migrated:
            await self._store.async_save(normalized_payload)

        controllers: list[ControllerConfig] = []
        for controller_data in normalized_payload.get("controllers", []):
            controllers.append(ControllerConfig.from_mapping(controller_data))
        return controllers

    async def async_save(self, controllers: list[ControllerConfig]) -> None:
        """Persist controller records to storage."""
        payload = {
            "version": STORAGE_VERSION,
            "controllers": [controller.as_dict() for controller in controllers],
        }
        await self._store.async_save(payload)

    async def async_upsert(self, controller: ControllerConfig) -> list[ControllerConfig]:
        """Insert or update a controller in storage."""
        controllers = await self.async_load()
        updated: list[ControllerConfig] = []
        replaced = False

        for existing in controllers:
            if existing.controller_id == controller.controller_id:
                updated.append(controller)
                replaced = True
                continue
            updated.append(existing)

        if not replaced:
            updated.append(controller)

        await self.async_save(updated)
        return updated

    async def async_delete(self, controller_id: str) -> list[ControllerConfig]:
        """Delete a controller from storage."""
        controllers = await self.async_load()
        updated = [
            controller
            for controller in controllers
            if controller.controller_id != controller_id
        ]
        await self.async_save(updated)
        return updated

    async def async_clear(self) -> None:
        """Remove all stored controllers after migration."""
        await self.async_save([])

    @staticmethod
    def _normalize_payload(payload: Any) -> tuple[dict[str, Any], bool]:
        """Normalize legacy payload shapes into the current schema."""
        if isinstance(payload, list):
            return {
                "version": STORAGE_VERSION,
                "controllers": payload,
            }, True

        if not isinstance(payload, dict):
            raise ValueError("Invalid storage payload type")

        controllers = payload.get("controllers")
        if not isinstance(controllers, list):
            return {
                "version": STORAGE_VERSION,
                "controllers": [],
            }, True

        normalized = {
            "version": STORAGE_VERSION,
            "controllers": controllers,
        }
        migrated = payload.get("version") != STORAGE_VERSION
        return normalized, migrated