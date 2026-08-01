#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_DIR="$ROOT_DIR/.ha_dev"
TARGET_COMPONENT_DIR="$CONFIG_DIR/custom_components/switchflow_controller"
SOURCE_COMPONENT_DIR="$ROOT_DIR/custom_components/switchflow_controller"

mkdir -p "$CONFIG_DIR/custom_components"
rm -rf "$TARGET_COMPONENT_DIR"
cp -R "$SOURCE_COMPONENT_DIR" "$TARGET_COMPONENT_DIR"

exec "$ROOT_DIR/.venv/bin/python" -m homeassistant -c "$CONFIG_DIR"