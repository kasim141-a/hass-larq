from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from pathlib import Path

import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

_LOGGER = logging.getLogger(__name__)
_DAILY_GOAL_ML = 2900
_VENV_PYTHON = "/config/larq_venv2/bin/python3"
_BATTERY_SCRIPT = "/config/custom_components/larq/larq_battery_read.py"
_ENTITY_PICTURE = "/local/larq-icon.png"

# Accept (and ignore) legacy refresh_token key so old config.yaml entries don't break setup
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional("refresh_token"): cv.string,
})


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info=None,
) -> None:
    async_add_entities([LarqDailyGoalSensor()])

    if not Path(_VENV_PYTHON).exists():
        _LOGGER.warning(
            "LARQ venv not found at %s — battery sensor will show 'unknown' until the "
            "venv is created. See README Part 2 for setup instructions.",
            _VENV_PYTHON,
        )

    coordinator = LarqBatteryCoordinator(hass)
    async_add_entities([LarqBatterySensor(coordinator)])
    hass.async_create_task(coordinator.async_refresh())


class LarqBatteryCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant) -> None:
        super().__init__(
            hass, _LOGGER, name="LARQ Battery", update_interval=timedelta(minutes=5)
        )

    async def _async_update_data(self) -> int | None:
        try:
            proc = await asyncio.create_subprocess_exec(
                _VENV_PYTHON, _BATTERY_SCRIPT,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        except asyncio.TimeoutError:
            _LOGGER.warning("LARQ battery read timed out — bottle may be out of range")
            return None
        except Exception as err:
            _LOGGER.warning("LARQ battery read error: %s", err)
            return None
        value = stdout.decode().strip()
        if not value.isdigit():
            _LOGGER.warning(
                "LARQ battery: no value returned — stderr: %s", stderr.decode()[:200]
            )
            return None
        return int(value)


class LarqDailyGoalSensor(SensorEntity):
    _attr_name = "LARQ Daily Goal"
    _attr_unique_id = "larq_daily_goal"
    _attr_native_unit_of_measurement = "mL"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:cup-water"
    _attr_entity_picture = _ENTITY_PICTURE
    _attr_native_value = _DAILY_GOAL_ML


class LarqBatterySensor(CoordinatorEntity, SensorEntity):
    _attr_name = "LARQ Battery"
    _attr_unique_id = "larq_battery"
    _attr_native_unit_of_measurement = "%"
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_picture = _ENTITY_PICTURE

    def __init__(self, coordinator: LarqBatteryCoordinator) -> None:
        super().__init__(coordinator)

    @property
    def available(self) -> bool:
        return True

    @property
    def native_value(self):
        return self.coordinator.data
