"""Config flow for the Wasteplan TRV integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
  TRVApiClient,
  TRVApiClientCommunicationError,
  TRVApiClientError,
)
from .const import CALENDAR_NAME, DOMAIN, LOCATION_ID, LOCATION_NAME, LOGGER


class TRVConfigFlow(ConfigFlow, domain=DOMAIN):
  """Handle config flow for Wasteplan TRV."""

  VERSION = 1

  def __init__(self) -> None:
    """Initialize the config flow."""
    self._locations: dict[str, str] = {}

  async def async_step_user(
    self,
    user_input: dict[str, Any] | None = None,
  ) -> ConfigFlowResult:
    """Ask for the address to search for."""
    errors: dict[str, str] = {}

    if user_input is not None:
      client = TRVApiClient(session=async_get_clientsession(self.hass))
      try:
        self._locations = await client.async_lookup_address(user_input[LOCATION_NAME])
      except TRVApiClientCommunicationError as exception:
        LOGGER.error(exception)
        errors["base"] = "connection"
      except TRVApiClientError:
        LOGGER.exception("Unexpected error looking up address")
        errors["base"] = "unknown"
      else:
        if self._locations:
          return await self.async_step_location()
        errors["base"] = "no_location"

    return self.async_show_form(
      step_id="user",
      data_schema=vol.Schema({vol.Required(LOCATION_NAME): str}),
      errors=errors,
    )

  async def async_step_location(
    self,
    user_input: dict[str, Any] | None = None,
  ) -> ConfigFlowResult:
    """Let the user pick one of the matching locations."""
    if user_input is not None:
      location_id = user_input[LOCATION_ID]
      self._async_abort_entries_match({LOCATION_ID: location_id})
      address = self._locations[location_id]

      return self.async_create_entry(
        title=address,
        data={
          CALENDAR_NAME: user_input[CALENDAR_NAME],
          LOCATION_NAME: address,
          LOCATION_ID: location_id,
        },
      )

    return self.async_show_form(
      step_id="location",
      data_schema=vol.Schema(
        {
          vol.Required(CALENDAR_NAME): str,
          vol.Required(LOCATION_ID): vol.In(self._locations),
        }
      ),
    )
