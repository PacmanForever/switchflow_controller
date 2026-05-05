"""Unit tests for the runtime manager."""

from __future__ import annotations

from types import MappingProxyType, SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from homeassistant.config_entries import ConfigSubentry
from homeassistant.exceptions import HomeAssistantError

from custom_components.switch_manager.manager import SwitchManagerRuntime
from custom_components.switch_manager.const import SUBENTRY_TYPE_CONTROLLER
from custom_components.switch_manager.models import ControllerConfig


def _controller(
    controller_id: str,
    *,
    enabled: bool = True,
    main_entity: str | None = None,
) -> ControllerConfig:
    return ControllerConfig.from_mapping(
        {
            "id": controller_id,
            "name": controller_id.title(),
            "main_entity": main_entity or f"light.{controller_id}",
            "wait_time": 60,
            "enabled": enabled,
        }
    )


class FakeRuntime:
    """Simple runtime double used to observe manager behavior."""

    created: list["FakeRuntime"] = []

    def __init__(self, hass, global_config, controller, entry_id) -> None:
        self.hass = hass
        self.global_config = global_config
        self.controller = controller
        self.entry_id = entry_id
        self.started = False
        self.stopped = False
        self.force_on = False
        self.force_off = False
        self.timer_reset = False
        FakeRuntime.created.append(self)

    async def async_start(self) -> None:
        self.started = True

    async def async_stop(self) -> None:
        self.stopped = True

    async def async_force_turn_on(self) -> None:
        self.force_on = True

    async def async_force_turn_off(self) -> None:
        self.force_off = True

    async def async_reset_timer(self) -> None:
        self.timer_reset = True


def _config_entry(*controllers: ControllerConfig, options: dict | None = None):
    subentries = {
        controller.controller_id: ConfigSubentry(
            data=MappingProxyType(
                {
                    key: value
                    for key, value in controller.as_dict().items()
                    if key not in {"id", "name"}
                }
            ),
            subentry_id=f"subentry-{controller.controller_id}",
            subentry_type=SUBENTRY_TYPE_CONTROLLER,
            title=controller.name,
            unique_id=controller.controller_id,
        )
        for controller in controllers
    }
    return SimpleNamespace(entry_id="entry-1", data={}, options=options or {}, subentries=subentries)


@pytest.mark.asyncio
async def test_async_setup_starts_only_enabled_controllers(hass, monkeypatch) -> None:
    """Setup should start runtimes only for enabled controllers."""

    FakeRuntime.created = []
    config_entry = _config_entry(_controller("hallway"), _controller("kitchen", enabled=False))
    runtime = SwitchManagerRuntime(hass, config_entry)
    monkeypatch.setattr("custom_components.switch_manager.manager.ControllerRuntime", FakeRuntime)

    await runtime.async_setup()

    assert set(runtime.controllers) == {"hallway", "kitchen"}
    assert set(runtime._controller_runtimes) == {"hallway"}
    assert len(FakeRuntime.created) == 1
    assert FakeRuntime.created[0].started is True


@pytest.mark.asyncio
async def test_async_unload_stops_all_active_runtimes(hass) -> None:
    """Unload should stop and clear all active runtimes."""

    config_entry = _config_entry()
    runtime = SwitchManagerRuntime(hass, config_entry)
    first = SimpleNamespace(async_stop=AsyncMock())
    second = SimpleNamespace(async_stop=AsyncMock())
    runtime._controller_runtimes = {"a": first, "b": second}

    await runtime.async_unload()

    first.async_stop.assert_awaited_once()
    second.async_stop.assert_awaited_once()
    assert runtime._controller_runtimes == {}


@pytest.mark.asyncio
async def test_async_reload_refreshes_global_config_and_reuses_setup(hass) -> None:
    """Reload should unload first, rebuild global config, and setup again."""

    config_entry = _config_entry(options={"smart_mode_entity": "binary_sensor.smart"})
    runtime = SwitchManagerRuntime(hass, config_entry)
    runtime.async_unload = AsyncMock()
    runtime.async_setup = AsyncMock()

    await runtime.async_reload()

    runtime.async_unload.assert_awaited_once()
    runtime.async_setup.assert_awaited_once()
    assert runtime.global_config.smart_mode_entity == "binary_sensor.smart"


def test_get_controller_returns_known_controller_and_raises_for_unknown(hass) -> None:
    """Controller lookups should be explicit and fail clearly."""

    config_entry = _config_entry()
    runtime = SwitchManagerRuntime(hass, config_entry)
    controller = _controller("hallway")
    runtime.controllers = {"hallway": controller}

    assert runtime.get_controller("hallway") is controller
    with pytest.raises(HomeAssistantError, match="Unknown controller id: missing"):
        runtime.get_controller("missing")


@pytest.mark.asyncio
async def test_async_set_controller_enabled_persists_and_reloads(hass) -> None:
    """Enabling or disabling should update the backing controller subentry."""

    config_entry = _config_entry(_controller("hallway", enabled=True))
    runtime = SwitchManagerRuntime(hass, config_entry)
    controller = _controller("hallway", enabled=True)
    runtime.controllers = {"hallway": controller}
    runtime._controller_subentries = {"hallway": config_entry.subentries["hallway"]}
    hass.config_entries.async_update_subentry = Mock(return_value=True)

    await runtime.async_set_controller_enabled("hallway", False)

    hass.config_entries.async_update_subentry.assert_called_once()
    updated_data = hass.config_entries.async_update_subentry.call_args.kwargs["data"]
    assert updated_data["enabled"] is False
    assert "id" not in updated_data
    assert "name" not in updated_data


@pytest.mark.asyncio
async def test_force_turn_on_and_off_build_ephemeral_runtime_when_missing(
    hass, monkeypatch
) -> None:
    """Force operations should create a temporary runtime when none is active."""

    FakeRuntime.created = []
    config_entry = _config_entry()
    runtime = SwitchManagerRuntime(hass, config_entry)
    runtime.controllers = {"hallway": _controller("hallway")}
    monkeypatch.setattr("custom_components.switch_manager.manager.ControllerRuntime", FakeRuntime)

    await runtime.async_force_turn_on("hallway")
    await runtime.async_force_turn_off("hallway")

    assert len(FakeRuntime.created) == 2
    assert FakeRuntime.created[0].force_on is True
    assert FakeRuntime.created[1].force_off is True


@pytest.mark.asyncio
async def test_force_turn_on_and_reset_use_existing_runtime(hass) -> None:
    """Active runtimes should be reused for imperative operations."""

    config_entry = _config_entry()
    runtime = SwitchManagerRuntime(hass, config_entry)
    runtime.controllers = {"hallway": _controller("hallway")}
    active_runtime = SimpleNamespace(
        async_force_turn_on=AsyncMock(),
        async_force_turn_off=AsyncMock(),
        async_reset_timer=AsyncMock(),
    )
    runtime._controller_runtimes = {"hallway": active_runtime}

    await runtime.async_force_turn_on("hallway")
    await runtime.async_force_turn_off("hallway")
    await runtime.async_reset_controller_timer("hallway")

    active_runtime.async_force_turn_on.assert_awaited_once()
    active_runtime.async_force_turn_off.assert_awaited_once()
    active_runtime.async_reset_timer.assert_awaited_once()


@pytest.mark.asyncio
async def test_reset_timer_requires_running_runtime(hass) -> None:
    """Resetting a timer should fail for a controller without active runtime."""

    config_entry = _config_entry()
    runtime = SwitchManagerRuntime(hass, config_entry)
    runtime.controllers = {"hallway": _controller("hallway")}

    with pytest.raises(
        HomeAssistantError, match="Controller hallway is disabled or not running"
    ):
        await runtime.async_reset_controller_timer("hallway")