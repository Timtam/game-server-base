"""Provides the Protocol class which is a subclass of
twisted.protocols.basic.LineReceiver until I figure out how the Telnet protocol
works."""

import logging
import sys
from typing import TYPE_CHECKING, Any, Optional, Tuple

from twisted.protocols.basic import LineReceiver
from twisted.python.failure import Failure

from .caller import Caller
from .parser import Parser

if TYPE_CHECKING:
    from .server import Server


class Protocol(LineReceiver):
    """
    Server protocol

    Instances of this class represent a connection to the server.

    server
    An instance of gsb.Server.
    host
    The IP address of the host which this connection represents.
    port
    The port number this connection is connected on.
    """

    def __init__(
        self,
        server: "Server",
        host: str,
        port: int,
        _parser: Parser,
        encode_args: Tuple[str, str] = (sys.getdefaultencoding(), "replace"),
        decode_args: Tuple[str, str] = (sys.getdefaultencoding(), "ignore"),
    ) -> None:

        super().__init__()

        self.server = server
        self.host = host
        self.port = port
        self._parser = _parser
        self.encode_args = encode_args
        self.decode_args = decode_args

    @property
    def parser(self) -> Optional[Parser]:
        """Get the current parser."""
        return self._parser

    @parser.setter
    def parser(self, value: Optional[Parser]) -> None:
        """Set self._parser."""
        old_parser = self._parser
        if old_parser is not None:
            old_parser.on_detach(self, value)
        if value is None:
            value = self.server.default_parser
            self.logger.warning(
                "Attempting to set parser to None. Falling back on %r.",
                self.server.default_parser,
            )
        self._parser = value
        print(value)
        value.on_attach(self, old_parser)

    def lineReceived(self, line: bytes) -> None:
        """Handle a line from a client."""
        line_str = line.decode(*self.decode_args)
        if self.parser:
            self.parser.handle_line(self, line_str)

    def connectionMade(self) -> None:
        """Call self.server.on_connect."""
        self.logger = logging.getLogger("%s:%d" % (self.host, self.port))
        self.server.connections.append(self)
        self.server.on_connect(Caller(self))
        if self.parser is not None:
            self.parser.on_attach(self, None)

    def connectionLost(self, reason: Failure) -> None:
        """Call self.server.on_disconnect."""
        if self in self.server.connections:
            self.server.connections.remove(self)
        self.logger.info("Disconnected: %s", reason.getErrorMessage())
        self.server.on_disconnect(Caller(self))

    def notify(self, *args: Any, **kwargs: Any) -> None:
        """Notify this connection of something."""
        self.server.notify(self, *args, **kwargs)
