"""Issue registry helpers for SwitchFlow Controller."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import slugify

from .const import DOMAIN, ISSUE_ID_PREFIX


def _build_issue_id(entry_id: str, field_name: str, entity_id: str) -> str:
    """Build a stable issue id for one configured entity problem per entry."""
    return (
        f"{ISSUE_ID_PREFIX}_{slugify(entry_id)}"
        f"_{slugify(field_name)}_{slugify(entity_id)}"
    )


def report_configured_entity_unavailable(
    hass: HomeAssistant,
    *,
    entry_id: str,
    controller_id: str,
    controller_name: str,
    field_name: str,
    entity_id: str,
) -> None:
    """Create or refresh a warning issue for an unavailable configured entity."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        _build_issue_id(entry_id, field_name, entity_id),
        is_fixable=False,
        is_persistent=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="configured_entity_unavailable",
        translation_placeholders={
            "controller_name": controller_name,
            "field_name": field_name,
            "entity_id": entity_id,
        },
        data={
            "entry_id": entry_id,
            "controller_id": controller_id,
            "field_name": field_name,
            "entity_id": entity_id,
        },
    )


def clear_configured_entity_issue(
    hass: HomeAssistant,
    *,
    entry_id: str,
    field_name: str,
    entity_id: str,
) -> None:
    """Clear a previously created warning issue when the entity recovers."""
    ir.async_delete_issue(
        hass,
        DOMAIN,
        _build_issue_id(entry_id, field_name, entity_id),
    )