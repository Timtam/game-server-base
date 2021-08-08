"""Provides the Parser class."""

import logging
import sys
from contextlib import contextmanager
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Iterable,
    Iterator,
    List,
    Optional,
    Tuple,
    Type,
    Union,
    overload,
)

if sys.version_info >= (3, 7):
    from re import Pattern
else:
    from re import _pattern_type as Pattern

from .caller import Caller, DontStopException
from .command import Command

if TYPE_CHECKING:
    from .protocol import Protocol

logger = logging.getLogger(__name__)


class Parser:
    """
    Used for parsing commands.
    """

    def __init__(
        self,
        command_separator: str = " ",
        command_class: Type[Command] = Command,
        default_args_regexp: Optional[str] = None,
        commands: Dict[str, List[Command]] = {},
        command_substitutions: Dict[str, str] = {},
    ):

        self.command_separator = command_separator
        self.command_class = command_class
        self.default_args_regexp = default_args_regexp
        self.commands = commands
        self.command_substitutions = command_substitutions

    def all_commands(self) -> List[Command]:
        """Get all the command objects present on this parser."""
        lst = list()
        for objects in self.commands.values():
            for cmd in objects:
                if cmd not in lst:
                    lst.append(cmd)
        return lst

    def huh(self, caller: Caller) -> bool:
        """Notify the connection that we have no idea what it's on about."""
        if caller.connection:
            caller.connection.notify("I don't understand that.")
        return True

    def on_attach(self, connection: "Protocol", old_parser: Optional["Parser"]) -> None:
        """This instance has been attached to connection to replace
        old_parser."""
        pass

    def on_detach(self, connection: "Protocol", new_parser: Optional["Parser"]) -> None:
        """This instance has been disconnected from connection and replaced by
        new_parser."""
        pass

    def on_error(self, caller: Caller) -> None:
        """An exception was raised by a command. In this instance caller has
        its exception attribute set to the exception which was thrown."""
        if caller.connection:
            caller.connection.notify("There was an error with your command.")

    def make_command_names(self, func: Callable[..., Any]) -> List[str]:
        """Get the name of a command from the name of a function."""
        return [getattr(func, "__name__", "command")]

    def make_command_description(self, func: Callable[..., None]) -> str:
        """Make a suitable description for a command."""
        return func.__doc__ or "No description available."

    def make_command_help(self, func: Callable[..., None]) -> str:
        """Make a suitable help message for a command."""
        return "No help available."

    @contextmanager
    def default_kwargs(self, **kwargs: Any) -> Iterator:
        """Decorator to automatically send kwargs to self.add_command."""

        def f(*a: Any, **kw: Any) -> Command:
            for key, value in kwargs.items():
                if key in kw:
                    logger.warning(
                        "Keyword argument %s specified twice: %r, %r.", key, kwargs, kw
                    )
                kw[key] = value
            return self.command(*a, **kw)

        try:
            logger.debug("Adding commands with default kwargs: %r.", kwargs)
            yield f
        finally:
            logger.debug("Context manager closing.")

    @overload
    def command(
        self,
        *,
        func: Callable[[Caller], None],
        names: Union[str, Iterable[str]] = "",
        description: str = "",
        help: str = "",
        args_regexp: Optional[Union[str, Pattern]] = None,
        allowed: Callable[[Caller], bool] = lambda c: True,
    ) -> Command:
        ...

    @overload
    def command(
        self,
        *,
        names: Union[str, Iterable[str]] = "",
        description: str = "",
        help: str = "",
        args_regexp: Optional[Union[str, Pattern]] = None,
        allowed: Callable[[Caller], bool] = lambda c: True,
    ) -> Callable[[Callable[[Caller], None]], Command]:
        ...

    def command(
        self,
        func: Optional[Callable[[Caller], None]] = None,
        names: Union[str, Iterable[str]] = "",
        description: str = "",
        help: str = "",
        args_regexp: Optional[Union[str, Pattern]] = None,
        allowed: Callable[[Caller], bool] = lambda c: True,
    ) -> Union[Command, Callable[[Callable[[Caller], None]], Command]]:
        """
        A decorator to add a command to this parser.

        Commands are made of instances of self.command_class.
        Arguments to the constructor will be guessed by the make_command_*
        methods of this parser.
        """

        def inner(func: Callable[[Caller], None]) -> Command:

            nonlocal names, description, help, args_regexp, allowed
            names = names or self.make_command_names(func)
            description = description or self.make_command_description(func)
            help = help or self.make_command_help(func)
            args_regexp = args_regexp or self.default_args_regexp
            c = self.command_class(
                func=func,
                names=names,
                description=description,
                help=help,
                args_regexp=args_regexp,
                allowed=allowed,
            )
            for name in c.names:
                lst = self.commands.get(name, [])
                lst.append(c)
                self.commands[name] = lst
            return c

        if func is None:
            return inner
        return inner(func)

    def pre_command(self, caller: Caller) -> bool:
        """Called before any command is sent. Should return True if the command
        is to be processed."""
        return True

    def split(self, line: str) -> Tuple[str, ...]:
        """Splits the command and returns (command, args). Both args and string
        should be strings."""
        split = line.split(self.command_separator, 1)
        if len(split) == 1:
            split.append(split[0].__class__())
        return tuple(split)

    def post_command(self, caller: Caller) -> None:
        """Called after 0 or more commands were matched."""
        pass

    def get_commands(self, name: str) -> List[Command]:
        """Get the commands named name."""
        return self.commands.get(name, [])

    def explain_substitution(
        self, connection: "Protocol", short: str, long: str
    ) -> None:
        """Explain command substitutions."""
        connection.notify(
            'Instead of typing "%s%s", you can type %s.',
            long,
            self.command_separator,
            short,
        )

    def explain(self, command: Command, connection: "Protocol") -> None:
        """Explain command to connection."""
        connection.notify("%s:", " or ".join(command.names))
        for key, value in self.command_substitutions.items():
            if value in command.names:
                self.explain_substitution(connection, key, value)
        connection.notify(command.description)
        connection.notify(command.help)

    def handle_line(self, connection: "Protocol", line: str) -> Optional[int]:
        """Handle a line of textt from a connection. If no commands are found
        then self.huh is called with caller."""
        if line and line[0] in self.command_substitutions:
            line = (
                self.command_substitutions[line[0]] + self.command_separator + line[1:]
            )
        caller = Caller(connection, text=line)
        if not self.pre_command(caller):
            return None
        command, args = self.split(line)
        caller.command = command
        caller.args_str = args
        commands = 0  # The number of matched commands.
        for cmd in self.get_commands(command):
            if cmd.ok_for(caller):
                if cmd.args_regexp is None:
                    caller.args = ()
                    caller.kwargs = {}
                else:
                    m = cmd.args_regexp.match(args)
                    if m is None:
                        if caller.connection:
                            self.explain(cmd, caller.connection)
                        break
                    caller.args = m.groups()
                    caller.kwargs = m.groupdict()
                commands += 1
                try:
                    cmd.func(caller)
                    break
                except DontStopException:
                    continue
                except Exception as e:
                    logger.warning("Error caught by %r from command %r:", self, cmd)
                    logger.exception(e)
                    caller.exception = e
                    self.on_error(caller)
        else:
            if not commands:
                self.huh(caller)
        if commands:
            return commands
        return None
