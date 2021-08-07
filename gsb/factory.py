"""Provides the Factory class which is a subclass of
twisted.internet.protocol.ServerFactory."""

import logging
from typing import TYPE_CHECKING, Optional, Type

from twisted.internet.interfaces import IAddress
from twisted.internet.protocol import ServerFactory

from .protocol import Protocol

if TYPE_CHECKING:
    from .server import Server

logger = logging.getLogger(__name__)


class Factory(ServerFactory):
    """
    The server factory.

    server
    The instance of Server which this factory is connected to.
    protocol
    The protocol class to use with buildConnection.
    """

    def __init__(self, server: "Server", protocol: Type[Protocol] = Protocol) -> None:

        self.server = server
        self.protocol = protocol

    def buildProtocol(self, addr: IAddress) -> Optional[Protocol]:
        if self.server.is_banned(addr.host):
            logger.warning(
                "Blocked incoming connection from banned host %s.", addr.host
            )
            return None
        else:
            logger.info("Incoming connection from %s:%d.", addr.host, addr.port)
            return self.protocol(
                self.server, addr.host, addr.port, self.server.default_parser
            )
