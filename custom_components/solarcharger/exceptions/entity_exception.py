"""Entity Exception."""


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class EntityExceptionError(Exception):
    """Exception raised for entity errors."""

    # ----------------------------------------------------------------------------
    def __init__(self, msg: str) -> None:
        """Initialize Entity Exception with a message."""
        super().__init__(msg)
        self.msg = msg
