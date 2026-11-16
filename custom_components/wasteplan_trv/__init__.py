"""Wasteplan TRV integration."""
from __future__ import annotations

from datetime import date, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.storage import Store
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

STORAGE_VERSION = 1


def _storage_key(entry: ConfigEntry) -> str:
  """Return the storage key for an entry's cached calendar."""
  return f"{DOMAIN}.{entry.entry_id}"


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


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
  """Delete the cached calendar when the entry is removed."""
  await Store(hass, STORAGE_VERSION, _storage_key(entry)).async_remove()


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
    self._store: Store[list[dict[str, str]]] = Store(hass, STORAGE_VERSION, _storage_key(entry))
    self._using_cache = False

  async def _async_update_data(self) -> list[Pickup]:
    """Fetch the pickup calendar, falling back to the last known one while TRV is down."""
    try:
      pickups = await self.client.async_get_pickups(self.location_id)
    except TRVApiClientError as exception:
      cached = self.data if self.data is not None else await self._async_load_cache()
      if cached is None:
        raise UpdateFailed(str(exception)) from exception
      if not self._using_cache:
        LOGGER.warning("TRV is unavailable, showing the last known calendar: %s", exception)
        self._using_cache = True
      return cached

    if self._using_cache:
      LOGGER.info("TRV is available again")
      self._using_cache = False
    if pickups != self.data:
      await self._store.async_save(
        [{"day": pickup.day.isoformat(), "waste_type": pickup.waste_type} for pickup in pickups]
      )
    return pickups

  async def _async_load_cache(self) -> list[Pickup] | None:
    """Load the last known calendar from disk."""
    if (data := await self._store.async_load()) is None:
      return None
    try:
      return [Pickup(date.fromisoformat(item["day"]), item["waste_type"]) for item in data]
    except (KeyError, TypeError, ValueError):
      LOGGER.warning("Ignoring unreadable calendar cache")
      return None


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
