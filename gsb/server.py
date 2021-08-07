"""Contains the Server base class."""

import logging
from datetime import datetime
from inspect import isclass
from types import MethodType
from typing import Any, List, Optional, Type, Union, cast

from twisted.internet import reactor

from .caller import Caller
from .parser import Parser
from .protocol import Protocol

try:
    from .ext.spell_checker_menu import SpellCheckerMenu
except ImportError:
    SpellCheckerMenu = None
from .factory import Factory as ServerFactory

logger = logging.getLogger(__name__)


class Server:
    """
    A game server instance.
    This class represents an instance of a game server.

    port
    The port the server should run on.
    interface
    The interface the server should listen on.
    factory
    The Twisted factory to use for dishing out connections.
    default_parser
    The default instance of Parser for new connections.
    connections
    A list of protocol objects that are connected.
    Started
    The time the server was started with Server.run.
    """

    def __init__(
        self,
        port: int = 4000,
        interface: str = "0.0.0.0",
        factory: Optional[ServerFactory] = None,
        default_parser: Parser = Parser(),
        connections: List[Protocol] = [],
        started: Optional[datetime] = None,
    ) -> None:

        self.port = port
        self.interface = interface
        self.factory = factory
        self.default_parser = default_parser
        self.connections = connections
        self.started = started

        if self.factory is None:
            self.factory = ServerFactory(self)

    def get_spell_checker(self, caller: Caller) -> Optional[Type[SpellCheckerMenu]]:
        """Return a class which can be used for spell checking. This function
        should return a class dispite the fact that it is called with a fully-
        formed caller."""
        return SpellCheckerMenu

    def is_banned(self, host: str) -> bool:
        """Determine if host is banned. Simply returns False by default."""
        return False

    def run(self) -> None:
        """Run the server."""
        if self.started is None:
            self.started = datetime.utcnow()
        reactor.listenTCP(self.port, self.factory, interface=self.interface)
        logger.info(
            "Now listening for connections on %s:%d.", self.interface, self.port
        )
        self.on_start(Caller(None))
        reactor.addSystemEventTrigger("before", "shutdown", self.on_stop, Caller(None))
        reactor.run()

    def on_start(self, caller: Caller) -> None:
        """The server has started. The passed instance of Caller does nothing,
        but ensures compatibility with the other events. Is called from
        Server.run."""
        pass

    def on_stop(self, caller: Caller) -> None:
        """The server is about to stop. The passed instance of Caller does
        nothing but maintains compatibility with the other events. Is scheduled
        when Server.run is used."""
        pass

    def on_connect(self, caller: Caller) -> None:
        """A connection has been established. Send welcome message ETC."""
        pass

    def on_disconnect(self, caller: Caller) -> None:
        """A client has disconnected."""
        pass

    def format_text(self, text: str, *args: Any, **kwargs: Any) -> str:
        """Format text for use with notify and broadcast."""
        if args:
            text = text % args
        if kwargs:
            text = text % kwargs
        return text

    def notify(
        self,
        connection: Protocol,
        text: Union[str, Parser, Type[Parser]],
        *args: Any,
        **kwargs: Any
    ) -> None:
        """Notify connection of text formatted with args and kwargs. Supports
        instances of, and the instanciation of Parser."""
        if connection is not None:
            if isclass(text) and issubclass(cast(Type[Parser], text), Parser):
                text = cast(Type[Parser], text)(*args, **kwargs)
            if isinstance(text, Parser):
                connection.parser = text
            else:
                connection.sendLine(
                    self.format_text(cast(str, text), *args, **kwargs).encode(
                        *connection.encode_args
                    )
                )

    def broadcast(self, text: str, *args: Any, **kwargs: Any) -> None:
        """Notify all connections."""
        text = self.format_text(text, *args, **kwargs)
        for con in self.connections:
            self.notify(con, text)

    def disconnect(self, connection: Protocol) -> None:
        """Disconnect a connection."""
        connection.transport.loseConnection()

    def event(self, func: MethodType) -> None:
        """A decorator to override methods of self."""
        name = func.__name__
        if not hasattr(self, name):
            raise AttributeError("No attribute named %s to override." % name)
        elif not isinstance(getattr(self, name), MethodType):
            raise TypeError("self.%s is not a method." % name)
        else:
            setattr(self, name, MethodType(func, self))
