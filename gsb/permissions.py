"""Various allow functions for use with commands."""

from typing import TYPE_CHECKING, Any, Callable, Iterator, Tuple

if TYPE_CHECKING:

    from .caller import Caller


def anyone(caller: "Caller") -> bool:
    """Always allow."""
    return True


class FuncPermission:
    """return self.func(x(caller) for x in self.validators"""

    def __init__(
        self,
        validators: Tuple[Callable[["Caller"], bool], ...],
        func: Callable[[Iterator[bool]], bool],
    ) -> None:

        self.validators = validators
        self.func = func

    def __call__(self, caller: "Caller") -> bool:
        return self.func(x(caller) for x in self.validators)


def and_(*validators: Callable[["Caller"], bool]) -> FuncPermission:
    """Ensure all validators pass."""
    return FuncPermission(validators, all)


def or_(*validators: Callable[["Caller"], bool]) -> FuncPermission:
    """Ensure any of the validators pass."""
    return FuncPermission(validators, any)
