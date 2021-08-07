"""Provides the Command class."""

import sys
from re import compile

if sys.version_info >= (3, 7):
    from re import Pattern
else:
    from re import _pattern_type as Pattern

from typing import Callable, Iterable, Optional, Union, cast

from .caller import Caller


class Command:
    """
    Command

    Instances of this class represent an entry in the Server.commands list.

    func
    The command function. This function will be called with an instance of
    Caller as its only argument assuming allow returns True.
    names
    1 or more names which describe this command.
    description
    A brief description of this command.
    help
    A help message for this command.
    args_regexp
    The regular expression which will match the arguments of this command, or
    None if no arguments are necessary.
    allowed
    A function which will be called with the same instance of Caller which
    will be used to call func. Should return True (the default) if it is okay
    to run this command, False otherwise.
    """

    def __init__(
        self,
        func: Callable[[Caller], None],
        names: Union[str, Iterable[str]],
        description: str,
        help: str,
        args_regexp: Optional[Union[str, Pattern]],
        allowed: Optional[Callable[[Caller], bool]],
    ) -> None:

        self.func = func
        self.names = names
        self.description = description
        self.help = help
        self.allowed = allowed
        self.args_regexp: Optional[Pattern] = None

        if args_regexp is not None:
            if not isinstance(args_regexp, Pattern):
                self.args_regexp = compile(args_regexp)
            else:
                self.args_regexp = args_regexp

        try:
            iter(names)
        except TypeError:
            self.names = [cast(str, self.names)]

    def ok_for(self, caller: Caller) -> bool:
        """Check if caller is allowed to access this command."""
        return self.allowed is None or self.allowed(caller)
