"""Constants for the Switch Manager integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "switch_manager"
TITLE: Final = "Switch Manager"

CONF_ACTIVATE_ON_DETECTION: Final = "activate_on_detection"
CONF_ALARM_ENTITY: Final = "alarm_entity"
CONF_ALARM_NOTIFICATION_SCRIPT_ENTITY: Final = "alarm_notification_script_entity"
CONF_ALARM_TIMER_ENTITY: Final = "alarm_timer_entity"
CONF_AREA_ID: Final = "area_id"
CONF_CONTROLLER_ID: Final = "id"
CONF_DETECTOR_SENSOR_1: Final = "detector_sensor_1"
CONF_DETECTOR_SENSOR_2: Final = "detector_sensor_2"
CONF_ENABLED: Final = "enabled"
CONF_ILLUMINANCE_SENSOR: Final = "illuminance_sensor"
CONF_ILLUMINANCE_THRESHOLD_ENTITY: Final = "illuminance_threshold_entity"
CONF_MAIN_ENTITY: Final = "main_entity"
CONF_NIGHT_ENTITY: Final = "night_entity"
CONF_NIGHT_MODE_ENTITY: Final = "night_mode_entity"
CONF_NOTIFY_WITH_ALARM: Final = "notify_with_alarm"
CONF_SMART_MODE_ENTITY: Final = "smart_mode_entity"
CONF_TURN_OFF_ENTITY_1: Final = "turn_off_entity_1"
CONF_TURN_OFF_ENTITY_2: Final = "turn_off_entity_2"
CONF_TURN_OFF_WHEN_PRESENCE_CLEARS: Final = "turn_off_when_presence_clears"
CONF_WAIT_TIME: Final = "wait_time"

DEFAULT_ILLUMINANCE_THRESHOLD: Final = 10.0
DEFAULT_WAIT_TIME_SECONDS: Final = 120

STORAGE_KEY: Final = f"{DOMAIN}.controllers"
STORAGE_VERSION: Final = 1
SUBENTRY_TYPE_CONTROLLER: Final = "controller"

DATA_MANAGER: Final = "manager"
ISSUE_ID_PREFIX: Final = "configured_entity_unavailable"
SERVICE_ENABLE_CONTROLLER: Final = "enable_controller"
SERVICE_DISABLE_CONTROLLER: Final = "disable_controller"
SERVICE_RESET_CONTROLLER_TIMER: Final = "reset_controller_timer"
SERVICE_FORCE_TURN_ON: Final = "force_turn_on"
SERVICE_FORCE_TURN_OFF: Final = "force_turn_off"