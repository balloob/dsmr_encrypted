"""The dsmr component."""

from asyncio import BaseTransport, CancelledError, Task
from collections.abc import Callable, Coroutine
from contextlib import suppress
from dataclasses import dataclass
from functools import partial
from typing import Any

from .dsmr_parser.clients.protocol import DSMRProtocol, create_dsmr_reader
from .dsmr_parser.clients.rfxtrx_protocol import (
    RFXtrxDSMRProtocol,
    create_rfxtrx_dsmr_reader,
)
from .dsmr_parser.objects import Telegram

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_PROTOCOL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_DSMR_VERSION,
    CONF_ENCRYPTION_KEY,
    DSMR_PROTOCOL,
    PLATFORMS,
)

type DsmrReaderFactory = Callable[
    [Callable[[Telegram], None]],
    Coroutine[Any, Any, tuple[BaseTransport, DSMRProtocol | RFXtrxDSMRProtocol]],
]


@dataclass
class DsmrState:
    """State of integration."""

    reader_factory: DsmrReaderFactory
    task: Task | None = None
    telegram: Telegram | None = None


type DsmrConfigEntry = ConfigEntry[DsmrState]


def _create_reader_factory(
    hass: HomeAssistant, entry: DsmrConfigEntry
) -> DsmrReaderFactory:
    """Build the DSMR reader factory for a config entry.

    Legacy network entries stored the host and port separately. They are
    combined into a single ``socket://host:port`` value here, in memory only;
    the stored entry is left untouched so downgrading Home Assistant keeps
    working. The serial library opens both local devices and such URLs.
    """
    port = entry.data[CONF_PORT]
    if CONF_HOST in entry.data:
        port = f"socket://{entry.data[CONF_HOST]}:{port}"

    # The encryption key is only supported by the standard DSMR reader.
    key_kwargs: dict[str, str] = {}
    if entry.data.get(CONF_PROTOCOL, DSMR_PROTOCOL) == DSMR_PROTOCOL:
        create_reader = create_dsmr_reader
        key_kwargs = {"encryption_key": entry.data.get(CONF_ENCRYPTION_KEY, "")}
    else:
        create_reader = create_rfxtrx_dsmr_reader

    return partial(
        create_reader,
        port,
        entry.data[CONF_DSMR_VERSION],
        loop=hass.loop,
        **key_kwargs,
    )


async def async_setup_entry(hass: HomeAssistant, entry: DsmrConfigEntry) -> bool:
    """Set up DSMR from a config entry."""

    @callback
    def _async_migrate_entity_entry(
        entity_entry: er.RegistryEntry,
    ) -> dict[str, Any] | None:
        """Migrate DSMR entity entry."""
        return async_migrate_entity_entry(entry, entity_entry)

    await er.async_migrate_entries(hass, entry.entry_id, _async_migrate_entity_entry)

    entry.runtime_data = DsmrState(reader_factory=_create_reader_factory(hass, entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: DsmrConfigEntry) -> bool:
    """Unload a config entry."""

    # Cancel the reconnect task
    if task := entry.runtime_data.task:
        task.cancel()
        with suppress(CancelledError):
            await task

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_update_options(hass: HomeAssistant, entry: DsmrConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)


@callback
def async_migrate_entity_entry(
    config_entry: ConfigEntry, entity_entry: er.RegistryEntry
) -> dict[str, Any] | None:
    """Migrate DSMR entity entries.

    - Migrates unique ID for sensors based on entity description name to key.
    """

    # Replace names with keys in unique ID
    for old, new in (
        ("Power_Consumption", "current_electricity_usage"),
        ("Power_Production", "current_electricity_delivery"),
        ("Power_Tariff", "electricity_active_tariff"),
        ("Energy_Consumption_(tarif_1)", "electricity_used_tariff_1"),
        ("Energy_Consumption_(tarif_2)", "electricity_used_tariff_2"),
        ("Energy_Production_(tarif_1)", "electricity_delivered_tariff_1"),
        ("Energy_Production_(tarif_2)", "electricity_delivered_tariff_2"),
        ("Power_Consumption_Phase_L1", "instantaneous_active_power_l1_positive"),
        ("Power_Consumption_Phase_L3", "instantaneous_active_power_l3_positive"),
        ("Power_Consumption_Phase_L2", "instantaneous_active_power_l2_positive"),
        ("Power_Production_Phase_L1", "instantaneous_active_power_l1_negative"),
        ("Power_Production_Phase_L2", "instantaneous_active_power_l2_negative"),
        ("Power_Production_Phase_L3", "instantaneous_active_power_l3_negative"),
        ("Short_Power_Failure_Count", "short_power_failure_count"),
        ("Long_Power_Failure_Count", "long_power_failure_count"),
        ("Voltage_Sags_Phase_L1", "voltage_sag_l1_count"),
        ("Voltage_Sags_Phase_L2", "voltage_sag_l2_count"),
        ("Voltage_Sags_Phase_L3", "voltage_sag_l3_count"),
        ("Voltage_Swells_Phase_L1", "voltage_swell_l1_count"),
        ("Voltage_Swells_Phase_L2", "voltage_swell_l2_count"),
        ("Voltage_Swells_Phase_L3", "voltage_swell_l3_count"),
        ("Voltage_Phase_L1", "instantaneous_voltage_l1"),
        ("Voltage_Phase_L2", "instantaneous_voltage_l2"),
        ("Voltage_Phase_L3", "instantaneous_voltage_l3"),
        ("Current_Phase_L1", "instantaneous_current_l1"),
        ("Current_Phase_L2", "instantaneous_current_l2"),
        ("Current_Phase_L3", "instantaneous_current_l3"),
        ("Max_power_per_phase", "belgium_max_power_per_phase"),
        ("Max_current_per_phase", "belgium_max_current_per_phase"),
        ("Energy_Consumption_(total)", "electricity_imported_total"),
        ("Energy_Production_(total)", "electricity_exported_total"),
    ):
        if entity_entry.unique_id.endswith(old):
            return {"new_unique_id": entity_entry.unique_id.replace(old, new)}

    # Replace unique ID for gas sensors, based on DSMR version
    old = "Gas_Consumption"
    if entity_entry.unique_id.endswith(old):
        dsmr_version = config_entry.data[CONF_DSMR_VERSION]
        if dsmr_version in {"4", "5", "5L"}:
            return {
                "new_unique_id": entity_entry.unique_id.replace(
                    old, "hourly_gas_meter_reading"
                )
            }
        if dsmr_version == "5B":
            return {
                "new_unique_id": entity_entry.unique_id.replace(
                    old, "belgium_5min_gas_meter_reading"
                )
            }
        if dsmr_version == "2.2":
            return {
                "new_unique_id": entity_entry.unique_id.replace(
                    old, "gas_meter_reading"
                )
            }

    # No migration needed
    return None
