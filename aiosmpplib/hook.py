from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from .log import TRACE, StructuredLogger
from .protocol import SmppMessage, SubmitSm
from .utils import check_param


class BaseHook(ABC):
    '''
    Interface that must be implemented to satisfy aiosmpplib hooks.
    User implementations should inherit this class and implement methods:
        :func:`to_smsc <BaseHook.to_smsc>` - before sending data to SMSC
        :func:`from_smsc <BaseHook.from_smsc>` - after receiving data from SMSC
        :func:`send_error <BaseHook.send_error>` - if error occured when building
        or transmitting SubmitSm message
    '''

    @abstractmethod
    async def to_smsc(self, smpp_message: SmppMessage, pdu: bytes) -> None:
        '''
        Called before sending data to SMSC.

        Parameters:
            smpp_message: Protocol message that is being sent
            pdu: The full PDU as sent to SMSC
        '''
        raise NotImplementedError()

    @abstractmethod
    async def from_smsc(self, smpp_message: Optional[SmppMessage], pdu: bytes) -> None:
        '''
        Called after receiving data from SMSC.

        Parameters:
            smpp_message: Protocol message that was received, or None if PDU couldn't be parsed
            pdu: Full PDU as received from SMSC
        '''
        raise NotImplementedError()

    @abstractmethod
    async def send_error(self, smpp_message: SubmitSm, error: Exception) -> None:
        '''
        Called after ther result of sending SubmitSm to SMSC is known (success or error).

        Parameters:
            smpp_message: Outgoing message
            error: Exception which occured (if None, message was accepted by SMSC).
                   It should be an instance of ValueError, or one of transport errors
                   (ConnectionError, OSError, TimeoutError, socket.error etc).
                   Whatever the error is, sending will not be retried automatically.
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

    async def to_smsc(self, smpp_message: SmppMessage, pdu: bytes) -> None:
        if self.logger.isEnabledFor(TRACE):
            self.logger.trace(TRACE, 'Sending message', pdu=pdu.hex(), **smpp_message.as_dict())

    async def from_smsc(self, smpp_message: Optional[SmppMessage], pdu: bytes) -> None:
        if self.logger.isEnabledFor(TRACE):
            params: Dict[str, Any] = smpp_message.as_dict() if smpp_message else {}
            self.logger.trace('Received message', pdu=pdu.hex(), **params)

    async def send_error(self, smpp_message: SubmitSm, error: Exception) -> None:
        if self.logger.isEnabledFor(TRACE):
            self.logger.trace('Send error occured', exc_info=error, **smpp_message.as_dict())
