"""Utilities."""

import asyncio
from collections.abc import Callable
import logging
import threading
from types import FrameType


def combined_conf_key(*conf_keys: list) -> str:
    """Combine configuration keys into a single string."""
    return ".".join(conf_keys)


def get_callable_name(obj: Callable) -> str:
    """Get the name as string of a callable object."""
    if isinstance(obj, property):
        return obj.fget.__name__ if obj.fget else "<UnknownProperty>"
    return obj.__name__


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
