"""Module to manage the charging process."""

import asyncio
from asyncio import Task, timeout
import inspect
import logging

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant

from ..const import WAIT_CHARGEE_UPDATE_HA, WAIT_CHARGEE_WAKEUP  # noqa: TID252
from ..utils import log_is_event_loop  # noqa: TID252
from .chargeable import Chargeable
from .charger import Charger

# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
_LOGGER = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class ChargeController:
    """Class to manage the charging process."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        config_subentry: ConfigSubentry,
        charger: Charger,
    ) -> None:
        """Initialize the Charge instance."""
        self.hass = hass
        self.config_entry = config_entry
        self.config_subentry = config_subentry
        self.device_name = config_subentry.unique_id
        self.charger = charger
        self.charge_task: Task | None = None
        self.end_charge_task: Task | None = None

    # ----------------------------------------------------------------------------
    @property
    def is_chargeable(self) -> bool:
        """Return True if the charger is chargeable."""
        return isinstance(self.charger, Chargeable)

    @property
    def get_chargee(self) -> Chargeable | None:
        """Return the chargeable device if applicable."""
        if self.is_chargeable:
            return self.charger  # type: ignore[return-value]
        return None

    # ----------------------------------------------------------------------------
    async def async_setup(self) -> None:
        """Async setup of the ChargeController."""
        await self.charger.async_setup()

    # ----------------------------------------------------------------------------
    async def async_unload(self) -> None:
        """Async unload of the ChargeController."""
        await self.charger.async_unload()

    # ----------------------------------------------------------------------------
    def start_charge(self) -> Task:
        """Start charge."""
        log_is_event_loop(_LOGGER, self.__class__.__name__, inspect.currentframe())

        # self.charge_task = self.config_entry.async_create_background_task(
        #     self.hass,
        #     self._async_start_charge_task(self.charger),
        #     "start_charge"
        # )

        if self.charge_task and not self.charge_task.done():
            _LOGGER.warning("Task %s already running", self.charge_task.get_name())
            return self.charge_task

        _LOGGER.info("Starting charge task for charger %s", self.device_name)
        self.charge_task = self.hass.async_create_task(
            self._async_start_charge(self.charger), f"{self.device_name} charge"
        )
        return self.charge_task

    # ----------------------------------------------------------------------------
    async def _async_start_charge(self, charger: Charger) -> None:
        """Async task to start the charger."""
        await self._async_start_charge_task(charger)

    # ----------------------------------------------------------------------------
    async def _async_start_charge_task(self, charger: Charger) -> None:
        """Async task to start the charging process."""
        log_is_event_loop(_LOGGER, self.__class__.__name__, inspect.currentframe())

        chargee: Chargeable | None = self.get_chargee

        if chargee:
            await chargee.async_wake_up_chargee()
            await asyncio.sleep(WAIT_CHARGEE_WAKEUP)
            await chargee.async_get_chargee_update()
            await asyncio.sleep(WAIT_CHARGEE_UPDATE_HA)

        while True:
            try:
                current_max = charger.get_max_charge_current()
                self.charge_devce(charger, chargee, current_max)
            except Exception as e:
                _LOGGER.error(
                    "Error in charge task for charger %s: %s", self.device_name, e
                )

            await asyncio.sleep(20)  # Wait before checking again
            break

    # ----------------------------------------------------------------------------
    def charge_devce(
        self, charger: Charger, chargee: Chargeable | None, current_max: float | None
    ) -> Task | None:
        """Charge device."""
        log_is_event_loop(_LOGGER, self.__class__.__name__, inspect.currentframe())

        current_now = charger.get_charge_current()
        _LOGGER.debug(
            "Charger %s current limit is %s A, max current is %s A",
            self.device_name,
            current_now,
            current_max,
        )

        try:
            if chargee:
                charge_limit = chargee.get_charge_limit()
                soc = chargee.get_state_of_charge()
                if soc is not None and charge_limit is not None:
                    if soc >= charge_limit:
                        _LOGGER.info(
                            "SOC %s %% is at or above charge limit %s %%, stopping charger %s",
                            soc,
                            charge_limit,
                            self.device_name,
                        )
                    else:
                        _LOGGER.debug(
                            "SOC %s %% is below charge limit %s %%, continuing charger %s",
                            soc,
                            charge_limit,
                            self.device_name,
                        )

        except TimeoutError:
            _LOGGER.warning(
                "Timeout while communicating with charger %s", self.device_name
            )
        except Exception as e:
            _LOGGER.error(
                "Error in charging task for charger %s: %s", self.device_name, e
            )

    # ----------------------------------------------------------------------------
    def stop_charge(self) -> Task | None:
        """Stop charge."""
        log_is_event_loop(_LOGGER, self.__class__.__name__, inspect.currentframe())

        if self.charge_task:
            if not self.charge_task.done():
                if self.end_charge_task:
                    if not self.end_charge_task.done():
                        _LOGGER.warning(
                            "Task %s already running", self.end_charge_task.get_name()
                        )
                        return self.end_charge_task

                _LOGGER.info("Ending charge task for charger %s", self.device_name)
                self.end_charge_task = self.hass.async_create_task(
                    self._async_stop_charge(self.charger),
                    f"{self.device_name} end charge",
                )
                return self.end_charge_task

            _LOGGER.info("Task %s already completed", self.charge_task.get_name())
        else:
            _LOGGER.info(
                "No running charge task to stop for charger %s", self.device_name
            )
        return None

    # ----------------------------------------------------------------------------
    async def _async_stop_charge(self, charger: Charger) -> None:
        """Async task to start the charger."""
        await self._async_stop_charge_task(charger)

    # ----------------------------------------------------------------------------
    async def _async_stop_charge_task(self, charger: Charger) -> None:
        """Stop charge task."""
        if self.charge_task:
            if not self.charge_task.done():
                self.charge_task.cancel()
                try:
                    await self.charge_task
                except asyncio.CancelledError:
                    _LOGGER.info(
                        "Task %s cancelled successfully", self.charge_task.get_name()
                    )
                except Exception as e:
                    _LOGGER.error(
                        "Error stopping charge task for charger %s: %s",
                        self.device_name,
                        e,
                    )
            else:
                _LOGGER.info("Task %s already completed", self.charge_task.get_name())
