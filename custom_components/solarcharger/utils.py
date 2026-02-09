"""Utilities."""

import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta
import logging
import threading
from types import FrameType
from typing import Any

# import pytz
from homeassistant.core import CALLBACK_TYPE, State
from homeassistant.util.dt import as_local, parse_datetime

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
#
# Other possible values:
# state.state = 'above_horizon'
# ----------------------------------------------------------------------------
def convert_to_timezone_aware_datetime(utc_str: str) -> datetime:
    """Convert HA UTC time string to timezone-aware datetime object."""
    # Parse into a timezone-aware datetime
    # Time string in UTC, ie. 2025-11-05T08:26:32.189258+00:00

    # dt: datetime = datetime.fromisoformat(utc_str)
    # convert to UTC explicitly
    # dt_utc = dt.astimezone(ZoneInfo("UTC"))

    dt_utc: datetime = parse_datetime(utc_str, raise_on_error=True)

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
    return convert_to_timezone_aware_datetime(sun_attrib_time_str)


# ----------------------------------------------------------------------------
def get_is_sun_rising(caller: str, sun_state: State) -> bool:
    """Is sun rising?"""
    return get_sun_attribute_or_abort(caller, sun_state, "rising")


# ----------------------------------------------------------------------------
def get_sun_elevation(caller: str, sun_state: State) -> float:
    """Get sun elevation."""
    return get_sun_attribute_or_abort(caller, sun_state, "elevation")


# ----------------------------------------------------------------------------
def get_next_sunrise_time(caller: str, sun_state: State) -> datetime:
    """Get next sunrise time in local timezone."""
    utc_time = get_sun_attribute_time(caller, sun_state, "next_rising")
    return as_local(utc_time)


# ----------------------------------------------------------------------------
def get_next_sunset_time(caller: str, sun_state: State) -> datetime:
    """Get next sunset time in local timezone."""
    utc_time = get_sun_attribute_time(caller, sun_state, "next_setting")
    return as_local(utc_time)


# ----------------------------------------------------------------------------
# This is not correct.
# Sun elevation degree is not same as 180 degree horizon.
# Sun elevation degree rate of change varies with day of time and season.
def get_sec_per_degree_sun_elevation(caller: str, sun_state: State) -> float:
    """Get seconds per degree sun elevation for the today."""
    next_setting_local = get_next_sunset_time(caller, sun_state)
    next_rising_local = get_next_sunrise_time(caller, sun_state)

    if next_rising_local > next_setting_local:
        # Passed sunrise today
        from_time = next_rising_local - timedelta(days=1)
        to_time = next_setting_local
    else:
        # Tomorrow
        from_time = next_rising_local
        to_time = next_setting_local

    total_sunlight_seconds = to_time.timestamp() - from_time.timestamp()
    seconds_per_degree: float = total_sunlight_seconds / 180

    # sydney_tz = pytz.timezone("Australia/Sydney")
    # next_rising_sydney = next_rising_utc.astimezone(sydney_tz)
    # next_setting_sydney = next_setting_utc.astimezone(sydney_tz)
    # _LOGGER.info(
    #     "next_rising_sydney=%s, next_setting_sydney=%s, total_sunlight_seconds=%s",
    #     next_rising_sydney,
    #     next_setting_sydney,
    #     total_sunlight_seconds,
    # )

    return seconds_per_degree


# ----------------------------------------------------------------------------
def remove_callback_subscription(
    caller: str, unsub_callbacks: dict[str, CALLBACK_TYPE], callback_key: str
) -> CALLBACK_TYPE | None:
    """Remove callback subscription."""

    unsubscribe = unsub_callbacks.get(callback_key)
    if unsubscribe is not None:
        _LOGGER.warning("%s: Removed callback: %s", caller, callback_key)
        unsub_callbacks.pop(callback_key)

        try:
            unsubscribe()
        except Exception:
            _LOGGER.exception(
                "%s: Failed to unsubscribe callback: %s", caller, callback_key
            )

    else:
        _LOGGER.debug(
            "%s: Callback not exist for removal: %s",
            caller,
            callback_key,
        )

    return unsubscribe


# ----------------------------------------------------------------------------
def save_callback_subscription(
    caller: str,
    unsub_callbacks: dict[str, CALLBACK_TYPE],
    callback_key: str,
    subscription: CALLBACK_TYPE,
) -> None:
    """Save callback subscription."""
    # unsubscribe = remove_callback_subscription(caller, unsub_callbacks, callback_key)
    # if unsubscribe is not None:
    #     _LOGGER.warning(
    #         "%s: Removed and replaced existing callback: %s",
    #         caller,
    #         callback_key,
    #     )
    remove_callback_subscription(caller, unsub_callbacks, callback_key)
    unsub_callbacks[callback_key] = subscription
    _LOGGER.warning("%s: Saved callback: %s", caller, callback_key)


# ----------------------------------------------------------------------------
def remove_all_callback_subscriptions(
    caller: str,
    unsub_callbacks: dict[str, CALLBACK_TYPE],
) -> None:
    """Remove all callback subscriptions."""

    for callback_key, unsubscribe in list(unsub_callbacks.items()):
        try:
            unsubscribe()
        except Exception:
            _LOGGER.exception(
                "%s: Failed to unsubscribe callback: %s", caller, callback_key
            )

    unsub_callbacks.clear()


# ----------------------------------------------------------------------------
