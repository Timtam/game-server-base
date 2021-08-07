"""
Provides the intercept class, a couple of useful subclasses, and some useful
functions.

To Use them, simply send an instance of Intercept with any of the notify
functions.

You can also lazily create Intercept (or subclass) instances with notify:

con.notify(Intercept, ...)

The notify code will create the instance for you and do its thing.

Functions:
after
A contextmanager to use to call a function after a function.

For example:
with after(print, 'Done.'):
    # Do something.

Calls callback with *args and **kwargs after the body has been executed.
"""

from contextlib import contextmanager
from typing import Any, Callable, List, Optional, Union

from .caller import Caller
from .command import Command
from .parser import Parser
from .protocol import Protocol


class Intercept(Parser):
    """
    Use instances of this class to intercept normal command processing.

    Attributes:
    abort_command
    The command the user can use to abort this instance.
    no_abort
    Don't let the user use the abort command. Can either be a string or a
    callable with the standard signature.
    aborted
    Line of text sent when a connection successfully uses @abort. If this value
    is callable then it shal be treated like a hook and called with a valid
    Caller instance.
    prepared to take a caller as the only argument.
    restore_parser
    Set connection.parser to this value with a successful abort.

    When sending things which can either be a callable or a string (like
    self.no_abort for example), consider using self.send.
    """

    def __init__(
        self,
        abort_command: str = "@abort",
        aborted: str = "Aborted",
        no_abort: Optional[Callable[[Caller], bool]] = None,
        restore_parser: Optional[Parser] = None,
    ) -> None:

        super().__init__()

        self.abort_command = abort_command
        self.aborted = aborted
        self.no_abort = None
        self.restore_parser = None

    def send(self, value: Union[Callable[[Caller], None], str], caller: Caller) -> None:
        """If value is a callable call it with caller. Otherwise use
        caller.connection.notify to send it to a connection."""
        if callable(value):
            value(caller)
        elif caller.connection:
            caller.connection.notify(value)

    def do_abort(self, caller: Caller) -> bool:
        """Try to abort this caller."""
        if self.no_abort:
            self.send(self.no_abort, caller)
        else:
            self.send(self.aborted, caller)
            if caller.connection:
                caller.connection.parser = self.restore_parser
        return True

    def on_attach(self, connection: Protocol, old_parser: Optional[Parser]) -> None:
        """Explain this instance to connnection."""
        self.explain(connection)

    def huh(self, caller: Caller) -> bool:
        """Check for self.abort_command."""
        line = caller.text
        if line == self.abort_command:
            return self.do_abort(caller)
        else:
            return False

    def explain(self, connection: Protocol) -> None:  # type: ignore

        pass


class MenuItem:
    """A menu item.

    Attributes:
    text
    The Text which is printed to the client.
    func
    The function which is called when this item is matched. Should be prepared
    to take an instance of Caller as it's only argument.
    """

    def __init__(self, text: str, func: Callable[[Caller], None]) -> None:

        self.text = text
        self.func = func
        self.index = 0

    def __str__(self) -> str:
        """Return text suitable for printing to a connection."""
        return self.as_string()

    def as_string(self) -> str:
        """Get a string representation of this item."""
        return "[{0.index}] {0.text}".format(self)


class MenuLabel:
    """
    A menu heading.

    text
    The text to print to the user.
    after
    The MenuItem instance this label comes after or None if it's at the
    beginning.
    """

    def __init__(self, text: str, after: Optional[MenuItem]):

        self.text = text
        self.after = after

    def __str__(self) -> str:
        return self.text


class _MenuBase:
    """Provides the title and items attributes."""

    def __init__(
        self,
        title: str = "Select an item:",
        items: List[MenuItem] = [],
        labels: List[MenuLabel] = [],
        prompt: str = "Type a number or @abort to abort.",
        no_matches: Optional[Callable[[Caller], None]] = None,
        multiple_matches: Optional[Callable[[Caller, List[MenuItem]], None]] = None,
    ):

        self.title = title
        self.items = items
        self.labels = labels
        self.prompt = prompt
        self.no_matches = no_matches
        self.multiple_matches = multiple_matches


class Menu(Intercept, _MenuBase):
    """
    A menu object.

    Attributes:
    title
    The line which is sent before the options.
    items
    A list of MenuItem instances.
    labels
    A list of MenuLabel instances.
    prompt
    The line which is sent after all the options. Can also be a callable which
    accepts a Caller instance.
    no_matches
    The connection entered something, but it was invalid. This should be a
    callable and expect to be sent an instance of Caller as its only argument.
    Defaults to Menu._no_matches.
    multiple_matches
    The connection entered something which matched multiple results. This
    should be a caller and breaks convention by expecting 2 arguments: An
    instance of Caller and a list of the MenuItem instances which matched.
    Defaults to Menu._multiple_matches.
    persistent
    Don't use self.restore_parser if no match is found.
    """

    def __init__(
        self,
        title: str = "Select an item:",
        items: List[MenuItem] = [],
        labels: List[MenuLabel] = [],
        prompt: str = "Type a number or @abort to abort.",
        no_matches: Optional[Callable[[Caller], None]] = None,
        multiple_matches: Optional[Callable[[Caller, List[MenuItem]], None]] = None,
        persistent: bool = False,
    ) -> None:

        Intercept.__init__(self)
        _MenuBase.__init__(
            self,
            title=title,
            items=items,
            labels=labels,
            prompt=prompt,
            no_matches=no_matches,
            multiple_matches=multiple_matches,
        )

        self.persistent = persistent

        for item in self.items:
            item.index = self.items.index(item) + 1

    def add_label(self, text: str, after: Optional[MenuItem]) -> MenuLabel:
        """Add a label."""
        lbl = MenuLabel(text, after)
        self.labels.append(lbl)
        return lbl

    def item(self, name):
        """A decorator to add an item with the specified name."""

        def inner(func):
            """Add the item."""
            i = MenuItem(name, func)
            self.items.append(i)
            self.__attrs_post_init__()
            return i

        return inner

    def explain(self, connection: Protocol) -> None:  # type: ignore
        """Explain this menu to connection."""
        connection.notify(self.title)
        self.send_items(connection)
        self.send(self.prompt, Caller(connection))

    def send_items(self, connection: Protocol, items: Optional[List[MenuItem]] = None):
        """Send the provided items to connection. If items is None use
        self.items."""
        if items is None:
            items = self.items
        for label in self.labels:
            if label.after is None:
                connection.notify(label.text)
        for i in items:
            connection.notify(i.as_string())
            for label in self.labels:
                if label.after is i:
                    connection.notify(label.text)

    def _no_matches(self, caller: Caller) -> None:
        """The connection sent something but it doesn't match any of this menu's
        items."""

        if caller.connection:
            caller.connection.notify("Invalid selection.")
            if not self.persistent:
                caller.connection.parser = self.restore_parser

    def _multiple_matches(self, caller: Caller, matches: List[MenuItem]) -> None:
        """The connection entered something but it matches multiple items."""
        connection = caller.connection

        if connection:
            connection.notify("That matched multiple items:")
            self.send_items(connection, items=matches)
            connection.notify(self.prompt)

    def huh(self, caller: Caller) -> bool:
        """Search for a match in self.items."""
        if super().huh(caller):
            return True
        m = self.match(caller)
        if m is not None:
            if caller.connection:
                caller.connection.parser = self.restore_parser
            m.func(caller)
        else:
            if self.persistent and caller.connection:
                self.explain(caller.connection)
        return True

    def match(self, caller: Caller) -> Optional[MenuItem]:
        """Sent by the server when a menu is found. Returns either an item or
        None if no or multiple matches were found (a case which is handled by
        this function)."""

        if not caller.text:
            return None

        text = caller.text.lower()
        if text == "$":  # Return the last item.
            return self.items[-1]
        try:
            num = int(text)
            if num > 0:
                num -= 1
            return self.items[num]
        except (ValueError, IndexError):
            items = []
            if text:
                for item in self.items:
                    if item.text.lower().startswith(text):
                        items.append(item)
            if not items:  # No matches
                if self.no_matches is None:
                    self._no_matches(caller)
                else:
                    self.no_matches(caller)
            elif len(items) == 1:  # Result!
                return items[0]
            else:  # Multiple matches.
                if self.multiple_matches is None:
                    self._multiple_matches(caller, items)
                else:
                    self.multiple_matches(caller, items)

        return None


class _ReaderBase:
    """Provides the positional attributes of Reader."""

    def __init__(self, done: Optional[Callable[[Caller], None]]) -> None:

        self.done = done


class Reader(Intercept, _ReaderBase):
    """Read 1 or more lines from the user.

    Attributes:
    done
    The function to call when we're done. Should be prepared to receive an
    instance of Caller with it's text attribute set to the contents of the
    buffer. This function will be called after 1 line of text if self.multiline
    evaluates to False or when a full stop (.) is received on its own.
    prompt
    Sent by self.explain. Can be either a string or a callable which will be
    sent an instance of Caller as its only argument. The caller's text
    attribute will be set to the text of this reader.
    line_separator
    The text to join lines of self.buffer with.
    done_command
    The command which is used to finish multiline entry.
    spell_check_command
    The command which is used to enter the spell checker if it is available.
    multiline
    Whether or not this Reader instance expects multiple lines. If True, keep
    collecting lines until self.done_command is received.
    before_line
    Sent before every new line. Can be either a string or a callable which will
    be sent an instance of Caller as its only argument. The caller's text
    attribute will be set to the text of this reader.
    after_line
    Sent after a line is received. Can be either a string or a callable which
    will be sent an instance of Caller as its only argument. The caller's text
    attribute will be set to the text of this reader.
    buffer
    The text received so far.
    """

    def __init__(
        self,
        prompt: Optional[Union[str, Callable[[Caller], None]]] = None,
        line_separator: str = "\n",
        done_command: str = ".",
        spell_check_command: str = ".spell",
        multiline: bool = False,
        before_line: Optional[Union[str, Callable[[Caller], None]]] = None,
        after_line: Optional[Union[str, Callable[[Caller], None]]] = None,
        buffer: str = "",
        done: Optional[Callable[[Caller], None]] = None,
    ):

        _ReaderBase.__init__(self, done=done)
        Intercept.__init__(self)

        self.prompt = prompt
        self.line_separator = line_separator
        self.done_command = done_command
        self.spell_check_command = spell_check_command
        self.multiline = multiline
        self.before_line = before_line
        self.after_line = after_line
        self.buffer = buffer

    def explain(self, connection: Protocol) -> None:  # type: ignore
        """Explain this reader."""
        caller = Caller(connection, text=self.buffer)
        if self.prompt is None:
            if self.multiline:
                connection.notify(
                    "Enter lines of text. Type %s on a blank " "line to finish%s.",
                    self.done_command,
                    (" or %s to exit" % self.abort_command)
                    if self.no_abort is None
                    else "",
                )
            else:
                connection.notify(
                    "Enter a line of text%s.",
                    (" or %s to exit" % self.abort_command)
                    if self.no_abort is None
                    else "",
                )
        else:
            self.send(self.prompt, caller)
        if self.before_line is not None:
            self.send(self.before_line, caller)

    def huh(self, caller: Caller) -> bool:
        """Add the line of text to the buffer."""
        line = caller.text
        if self.after_line is not None:
            self.send(self.after_line, caller)
        if super().huh(caller):
            return True
        if caller.connection:
            if line == self.spell_check_command:
                m = caller.connection.server.get_spell_checker(caller)
                if m is not None:
                    caller.connection.notify(
                        m, self.buffer, self.restore, restore_parser=None
                    )
                else:
                    caller.connection.notify(
                        "Spell checking is not available on this system."
                    )
                return True
            elif not self.multiline or line != self.done_command:
                if self.buffer and line:
                    self.buffer = self.line_separator.join([self.buffer, line])
                elif caller.text:
                    self.buffer = caller.text
            caller.text = self.buffer
            if not self.multiline or line == self.done_command:
                caller.connection.parser = self.restore_parser
                if self.done:
                    self.done(caller)
                return True
            else:
                if self.before_line is not None:
                    self.send(self.before_line, caller)
        return False

    def restore(self, caller: Caller) -> None:
        """Restore from a spell checker menu."""
        if caller.connection:
            caller.connection.notify("Spell checking complete.")
            caller.connection.parser = self

        if caller.text:
            self.buffer = caller.text


class _YesOrNoBase:
    """The base which makes up the YesOrNo class."""

    def __init__(self, question: str, yes: Callable[[Caller], None]) -> None:

        self.question = question
        self.yes = yes


class YesOrNo(Intercept, _YesOrNoBase):
    """Send this to a connection to ask a simple yes or no question.

    attributes:
    question
    The question you want to ask.
    yes
    The function which is called when the user answers in the afirmative.
    no
    The function which is called when the user answers no.
    prompt
    The prompt which is sent after the question to tell the user what to do.
    """

    def __init__(
        self,
        question: str,
        yes: Callable[[Caller], None],
        no: Optional[Callable[[Caller], None]] = None,
        prompt: Optional[str] = None,
    ):

        Intercept.__init__(self)
        _YesOrNoBase.__init__(self, question=question, yes=yes)

        self.no = no
        self.prompt = prompt

        if self.prompt is None:
            self.prompt = (
                'Enter "yes" or "no" or %s to abort the command.' % self.abort_command
            )

    def explain(self, connection: Protocol) -> None:  # type: ignore
        """Send the connection our question."""
        connection.notify(self.question)
        connection.notify(self.prompt)

    def huh(self, caller: Caller) -> bool:
        """Check for yes or no."""
        if not super().huh(caller):
            if caller.text:
                if caller.connection:
                    caller.connection.parser = self.restore_parser
                if caller.text.lower().startswith("y"):
                    self.yes(caller)
                else:
                    if self.no is not None:
                        self.no(caller)
                    else:
                        self.do_abort(caller)

                return True
        return False


@contextmanager
def after(_f: Callable[..., None], *args: Any, **kwargs: Any):
    """Call _f(*args, **kwargs) after everything else has been done."""
    yield
    _f(*args, **kwargs)
