from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from .log import TRACE, StructuredLogger
from .protocol import SmppMessage
from .utils import check_param


class BaseHook(ABC):
    '''
    Interface that must be implemented to satisfy aiosmpplib hooks.
    User implementations should inherit this class and implement methods:
        :func:`sending <BaseHook.sending>` - Called before sending data to SMPP peer
        :func:`received <BaseHook.received>` - Called after receiving data from SMPP peer
        :func:`send_error <BaseHook.send_error>` - Called if error occured when building
        or transmitting SubmitSm message
    '''

    @abstractmethod
    async def sending(self, smpp_message: SmppMessage, pdu: bytes, client_id: str) -> None:
        '''
        Called before sending data to SMPP peer.

        Parameters:
            smpp_message: Protocol message that is being sent
            pdu: The full PDU as sent to SMPP peer
            client_id: Client ID
        '''
        raise NotImplementedError()

    @abstractmethod
    async def received(self, smpp_message: Optional[SmppMessage], pdu: bytes,
                       client_id: str) -> None:
        '''
        Called after receiving data from SMPP peer.

        Parameters:
            smpp_message: Protocol message that was received, or None if PDU couldn't be parsed
            pdu: Full PDU as received from SMPP peer
            client_id: Client ID
        '''
        raise NotImplementedError()

    @abstractmethod
    async def send_error(self, smpp_message: SmppMessage, error: Exception, client_id: str) -> None:
        '''
        Called if error occured when building or transmitting SubmitSm message.

        Parameters:
            smpp_message: Outgoing message
            error: Exception which occured (if None, message was accepted by SMSC).
                   It should be an instance of ValueError, or one of transport errors
                   (ConnectionError, OSError, TimeoutError, socket.error etc).
                   Whatever the error is, sending will not be retried automatically.
            client_id: Client ID
        '''
        raise NotImplementedError()


class SimpleHook(BaseHook):
    '''
    This is an implementation of BaseHook.
    When this class is called, it just logs the request or response.
    '''

    def __init__(self, logger: StructuredLogger) -> None:
        check_param(logger, 'logger', StructuredLogger)
        self.logger: StructuredLogger = logger

    async def sending(self, smpp_message: SmppMessage, pdu: bytes, client_id: str) -> None:
        if self.logger.isEnabledFor(TRACE):
            self.logger.trace(TRACE, 'Sending message', pdu=pdu.hex(), **smpp_message.as_dict())

    async def received(self, smpp_message: Optional[SmppMessage], pdu: bytes,
                       client_id: str) -> None:
        if self.logger.isEnabledFor(TRACE):
            params: Dict[str, Any] = smpp_message.as_dict() if smpp_message else {}
            self.logger.trace('Received message', pdu=pdu.hex(), **params)

    async def send_error(self, smpp_message: SmppMessage, error: Exception, client_id: str) -> None:
        if self.logger.isEnabledFor(TRACE):
            self.logger.trace('Send error occured', exc_info=error, **smpp_message.as_dict())
