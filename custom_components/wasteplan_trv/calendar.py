"""Support for Wasteplan TRV calendar."""
from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import TRVDataUpdateCoordinator, TRVEntity
from .api import Pickup
from .const import CALENDAR_NAME, DOMAIN, LOCATION_ID, LOCATION_NAME

# TRV only gives a date, so show each pickup as a 08:00-16:00 event.
PICKUP_START_HOUR = 8
PICKUP_DURATION = timedelta(hours=8)


async def async_setup_entry(
  hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
  """Set up Wasteplan calendars based on a config entry."""
  coordinator: TRVDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
  async_add_entities([TRVCalendar(coordinator, entry)])


class TRVCalendar(TRVEntity, CalendarEntity):
  """Define a Wasteplan calendar."""

  _attr_icon = "mdi:delete-empty"

  def __init__(
    self,
    coordinator: TRVDataUpdateCoordinator,
    entry: ConfigEntry,
  ) -> None:
    """Initialize the Wasteplan entity."""
    super().__init__(coordinator, entry)
    self._attr_unique_id = entry.data[LOCATION_ID]
    self._attr_name = entry.data[CALENDAR_NAME]
    self._location: str = entry.data[LOCATION_NAME]

  @property
  def event(self) -> CalendarEvent | None:
    """Return the current or next upcoming pickup."""
    now = dt_util.now()
    return next((event for event in self._events() if event.end > now), None)

  async def async_get_events(
    self,
    hass: HomeAssistant,
    start_date: datetime,
    end_date: datetime,
  ) -> list[CalendarEvent]:
    """Return calendar events within a datetime range."""
    return [
      event
      for event in self._events()
      if event.start < end_date and event.end > start_date
    ]

  def _events(self) -> list[CalendarEvent]:
    """Return all pickups as calendar events, sorted by start."""
    return [self._to_event(pickup) for pickup in self.coordinator.data]

  def _to_event(self, pickup: Pickup) -> CalendarEvent:
    """Convert a pickup to a calendar event."""
    start = dt_util.start_of_local_day(pickup.day).replace(hour=PICKUP_START_HOUR)
    return CalendarEvent(
      summary=pickup.waste_type,
      start=start,
      end=start + PICKUP_DURATION,
      location=self._location,
    )
