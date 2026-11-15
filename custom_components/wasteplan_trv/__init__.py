"""Wasteplan TRV integration."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import (
  CoordinatorEntity,
  DataUpdateCoordinator,
  UpdateFailed,
)

from .api import (
  Pickup,
  TRVApiClient,
  TRVApiClientError,
)
from .const import ATTRIBUTION, DOMAIN, LOCATION_ID, LOGGER

PLATFORMS: list[Platform] = [
  Platform.CALENDAR,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
  """Set up this integration using UI."""
  coordinator = TRVDataUpdateCoordinator(
    hass=hass,
    entry=entry,
    client=TRVApiClient(session=async_get_clientsession(hass)),
  )

  await coordinator.async_config_entry_first_refresh()

  hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
  await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

  return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
  """Handle removal of an entry."""
  if unloaded := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
    hass.data[DOMAIN].pop(entry.entry_id)
  return unloaded


class TRVDataUpdateCoordinator(DataUpdateCoordinator[list[Pickup]]):
  """Class to manage fetching data from the API."""

  def __init__(
    self,
    hass: HomeAssistant,
    entry: ConfigEntry,
    client: TRVApiClient,
  ) -> None:
    """Initialize."""
    super().__init__(
      hass=hass,
      logger=LOGGER,
      config_entry=entry,
      name=DOMAIN,
      update_interval=timedelta(hours=5),
    )
    self.client = client
    self.location_id: str = entry.data[LOCATION_ID]

  async def _async_update_data(self) -> list[Pickup]:
    """Fetch the pickup calendar from TRV."""
    try:
      return await self.client.async_get_pickups(self.location_id)
    except TRVApiClientError as exception:
      raise UpdateFailed(str(exception)) from exception


class TRVEntity(CoordinatorEntity[TRVDataUpdateCoordinator]):
  """Representation of a Wasteplan entity."""

  _attr_attribution = ATTRIBUTION

  def __init__(
    self,
    coordinator: TRVDataUpdateCoordinator,
    entry: ConfigEntry,
  ) -> None:
    """Initialize Wasteplan entity."""
    super().__init__(coordinator=coordinator)
    self._attr_device_info = DeviceInfo(
      identifiers={(DOMAIN, str(entry.data[LOCATION_ID]))},
      entry_type=DeviceEntryType.SERVICE,
      configuration_url="https://github.com/jonkristian/wasteplan_trv",
      manufacturer="Trondheim Renholdsverk",
      name="Trondheim Renholdsverk",
    )
