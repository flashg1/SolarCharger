"""Utilities."""

import asyncio
from collections.abc import Callable
from datetime import datetime
import logging
import threading
from types import FrameType
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.core import CALLBACK_TYPE, State

# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
_LOGGER = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# General utils
# ----------------------------------------------------------------------------
# def combined_conf_key(*conf_keys: list) -> str:
#     """Combine configuration keys into a single string."""
#     return ".".join(conf_keys)


# ----------------------------------------------------------------------------
def get_callable_name(obj: Callable) -> str:
    """Get the name as string of a callable object."""
    if isinstance(obj, property):
        return obj.fget.__name__ if obj.fget else "<UnknownProperty>"
    return obj.__name__


# ----------------------------------------------------------------------------
# Threading utils
# ----------------------------------------------------------------------------
def is_event_loop_thread():
    """Check if the current thread is the main event loop thread."""
    try:
        # Get the currently running event loop
        loop = asyncio.get_running_loop()

        # The main event loop is typically associated with the main thread
        # You can compare the thread ID of the loop with the current thread
        # However, directly comparing loop._thread_id is not officially supported
        # A more robust approach is to check if the loop is the global default loop
        # and if the current thread is the main thread.
        return (
            threading.current_thread() is threading.main_thread()
            and loop is asyncio.get_event_loop()
        )
    except RuntimeError:
        # No event loop is running in the current thread
        return False


# ----------------------------------------------------------------------------
def log_is_event_loop(
    logger: logging.Logger, classname: str, methodframe: FrameType | None
) -> None:
    """Log if running in event loop thread."""
    logger.debug(
        "%s %s is running in event loop thread: %s",
        classname,
        methodframe.f_code.co_name if methodframe else "<UnknownMethod>",
        is_event_loop_thread(),
    )


# ----------------------------------------------------------------------------
# Sun utils
# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
# state.state = 'below_horizon'
# state.attributes = {
#     "next_dawn": "2025-11-04T18:25:01.044505+00:00",
#     "next_dusk": "2025-11-05T08:53:46.360780+00:00",
#     "next_midnight": "2025-11-04T13:39:07+00:00",
#     "next_noon": "2025-11-05T01:39:06+00:00",
#     "next_rising": "2025-11-04T18:52:10.267297+00:00",
#     "next_setting": "2025-11-05T08:26:32.189258+00:00",
#     "elevation": -38.55,
#     "azimuth": 199.59,
#     "rising": False,
#     "friendly_name": "Sun",
# }
# ----------------------------------------------------------------------------
def convert_utc_time_string(utc_str: str) -> datetime:
    """Convert HA UTC time string to timezone-aware datetime object."""
    # Parse into a timezone-aware datetime
    # Time string in UTC, ie. 2025-11-05T08:26:32.189258+00:00
    dt = datetime.fromisoformat(utc_str)

    # convert to UTC explicitly
    dt_utc = dt.astimezone(ZoneInfo("UTC"))

    # HA Local timezone has been set to UTC, ie. dt_utc = dt_localtime
    # dt_localtime = dt_utc.astimezone()

    # Convert the string to a datetime object
    # format_string = "%Y-%m-%dT%H:%M:%S"
    # dt_utc = datetime.strptime(utc_str, format_string)

    # now_time = datetime.now()
    # now_time_sec = now_time.timestamp()

    return dt_utc


# ----------------------------------------------------------------------------
def get_sun_attribute_or_abort(caller: str, sun_state: State, attrib_name: str) -> Any:
    """Get sun attribute or abort."""
    sun_attrib = sun_state.attributes.get(attrib_name)
    if sun_attrib is None:
        raise ValueError(f"{caller}: Failed to get sun attribute '{attrib_name}'")
    _LOGGER.debug("%s: Sun %s=%s", caller, attrib_name, sun_attrib)

    return sun_attrib


# ----------------------------------------------------------------------------
def get_sun_attribute_time(caller: str, sun_state: State, attrib: str) -> datetime:
    """Get sun time attribute."""
    # sun_attrib_time_str in utc
    sun_attrib_time_str: str = get_sun_attribute_or_abort(caller, sun_state, attrib)
    return convert_utc_time_string(sun_attrib_time_str)


# ----------------------------------------------------------------------------
def get_next_sunrise_time(caller: str, sun_state: State) -> datetime:
    """Get next sunrise time."""
    return get_sun_attribute_time(caller, sun_state, "next_rising")


# ----------------------------------------------------------------------------
def get_next_sunset_time(caller: str, sun_state: State) -> datetime:
    """Get next sunset time."""
    return get_sun_attribute_time(caller, sun_state, "next_setting")


# ----------------------------------------------------------------------------
def get_sec_per_degree_sun_elevation(caller: str, sun_state: State) -> float:
    """Get seconds per degree sun elevation for the today."""
    next_setting_utc = get_next_sunset_time(caller, sun_state)
    next_setting_sec = next_setting_utc.timestamp()

    next_rising_utc = get_next_sunrise_time(caller, sun_state)
    next_rising_sec = next_rising_utc.timestamp()

    seconds_per_degree: float = abs(next_setting_sec - next_rising_sec) / 180

    return seconds_per_degree


# ----------------------------------------------------------------------------
def remove_callback_subscription(
    caller: str, unsub_callbacks: dict[str, CALLBACK_TYPE], callback_key: str
) -> CALLBACK_TYPE | None:
    """Remove callback subscription."""
    unsubscribe = unsub_callbacks.get(callback_key)
    if unsubscribe is not None:
        unsubscribe()
        unsub_callbacks.pop(callback_key)
        _LOGGER.debug("%s: Removed callback subscription: %s", caller, callback_key)
    else:
        _LOGGER.debug(
            "%s: Callback subscription not exist for removal: %s",
            caller,
            callback_key,
        )

    return unsubscribe


# ----------------------------------------------------------------------------
def save_callback_subscription(
    caller,
    unsub_callbacks: dict[str, CALLBACK_TYPE],
    callback_key: str,
    subscription: CALLBACK_TYPE,
) -> None:
    """Save callback subscription."""
    unsubscribe = remove_callback_subscription(caller, unsub_callbacks, callback_key)
    unsub_callbacks[callback_key] = subscription
    _LOGGER.debug("%s: Saved callback subscription: %s", caller, callback_key)

    if unsubscribe is not None:
        _LOGGER.warning(
            "%s: Removed and replaced unexpected existing callback: %s",
            caller,
            callback_key,
        )


# ----------------------------------------------------------------------------
def remove_all_callback_subscriptions(
    unsub_callbacks: dict[str, CALLBACK_TYPE],
) -> None:
    """Remove all callback subscriptions."""
    for unsubscribe in unsub_callbacks.values():
        unsubscribe()
    unsub_callbacks.clear()


# ----------------------------------------------------------------------------
