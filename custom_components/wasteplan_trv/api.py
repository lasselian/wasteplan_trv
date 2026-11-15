"""TRV API Client."""
from __future__ import annotations

import asyncio
from datetime import date, datetime
from typing import Any, NamedTuple

import aiohttp

API_BASE_URL = "https://trv.no/wp-json/wasteplan/v2"
REQUEST_TIMEOUT = 10


class TRVApiClientError(Exception):
  """Exception to indicate a general API error."""


class TRVApiClientCommunicationError(TRVApiClientError):
  """Exception to indicate a communication error."""


class Pickup(NamedTuple):
  """A scheduled waste pickup."""

  day: date
  waste_type: str


class TRVApiClient:
  """TRV API Client."""

  def __init__(self, session: aiohttp.ClientSession) -> None:
    """Initialize the API client."""
    self._session = session

  async def async_lookup_address(self, address: str) -> dict[str, str]:
    """Search TRV for an address. Returns a mapping of location ID to address."""
    data = await self._api_wrapper(f"{API_BASE_URL}/adress", params={"s": address})
    try:
      return {location["id"]: location["adresse"] for location in data}
    except (KeyError, TypeError) as exception:
      raise TRVApiClientError(f"Unexpected address data from TRV: {exception!r}") from exception

  async def async_get_pickups(self, location_id: str) -> list[Pickup]:
    """Get the upcoming pickups for a location, sorted by date."""
    data = await self._api_wrapper(f"{API_BASE_URL}/calendar/{location_id}")
    try:
      pickups = [
        Pickup(datetime.fromisoformat(item["dato"]).date(), item["fraksjon"])
        for item in data["calendar"] or []
      ]
    except (KeyError, TypeError, ValueError) as exception:
      raise TRVApiClientError(f"Unexpected calendar data from TRV: {exception!r}") from exception
    return sorted(pickups, key=lambda pickup: pickup.day)

  async def _api_wrapper(self, url: str, params: dict[str, str] | None = None) -> Any:
    """Fetch JSON from the API."""
    try:
      async with asyncio.timeout(REQUEST_TIMEOUT):
        async with self._session.get(url, params=params) as response:
          if response.status >= 400:
            message = f"TRV returned HTTP {response.status}"
            # TRV puts the useful part ("API timeout", "no calendar items found") in a JSON body.
            if response.content_type == "application/json":
              message += f": {(await response.text()).strip()[:200]}"
            raise TRVApiClientCommunicationError(message)
          return await response.json()
    except TimeoutError as exception:
      raise TRVApiClientCommunicationError("Timeout fetching data from TRV") from exception
    except aiohttp.ClientError as exception:
      raise TRVApiClientCommunicationError(f"Error fetching data from TRV: {exception}") from exception
    except ValueError as exception:
      raise TRVApiClientError("TRV returned invalid JSON") from exception
