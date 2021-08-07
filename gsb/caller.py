"""Provides the Caller class."""

from typing import TYPE_CHECKING, Any, Dict, Optional, Sequence, Type

if TYPE_CHECKING:

    from re import Match

    from .protocol import Protocol


class DontStopException(Exception):
    """The exception raised by Caller.dont_stop."""

    pass


class Caller:
    """A
    Caller

    Instances of this class represent a connection calling either a command
    provided with the Server.command decorator or an event such as
    Server.on_connect.

    connection
    The connection which initiated the action.
    text
    The full text of the command (or None if this is an event).
    command
    The command extracted from text.
    args_str
    The full string arguments from the command.
    match
    The match from the regularexpression which matched to call this command (or
    None if this is an event).
    args
    The result of match.groups()
    kwargs
    The result of match.groupdict()
    exception
    An exception which is set by on_error.
    """

    def __init__(
        self,
        connection: Optional["Protocol"],
        text: Optional[str] = None,
        command: str = "",
        args_str: str = "",
        match: Optional["Match"] = None,
        args: Sequence[Any] = (),
        kwargs: Dict = {},
        exception: Optional[Exception] = None,
    ):

        self.connection = connection
        self.text = text
        self.command = command
        self.args_str = args_str
        self.match = match
        self.args = args
        self.kwargs = kwargs
        self.exception = exception

    def dont_stop(self) -> None:
        """If called from a command the command interpreter will not stop
        hunting for matching commands."""
        raise DontStopException()
