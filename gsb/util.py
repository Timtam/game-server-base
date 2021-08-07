"""Various utility functions."""

from typing import Any, Callable, List, TypeVar

from .parser import Parser

FuncT = TypeVar("FuncT", bound=Callable[..., Any])


def command_parsers(parsers: List[Parser], **kwargs: Any) -> Callable[[FuncT], None]:
    """A decorator to add the same function to multiple parsers in the provided
    list."""

    def inner(func: FuncT) -> None:
        for parser in parsers:
            parser.command(**kwargs)(func)

    return inner
