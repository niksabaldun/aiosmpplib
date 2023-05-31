import time
from abc import ABC, abstractmethod
from typing import Dict, Optional, Tuple
from .hook import AbstractHook
from .protocol import SmppMessage, SubmitSm
from .state import SmppCommand
from .utils import check_param

_EXPIRED_ERROR: TimeoutError = TimeoutError('No response to command received within timeout')


class AbstractCorrelator(ABC):
    '''
    Interface that must be implemented to satisfy aiosmpplib Correlator.
    User implementations should inherit this class and
    implement the :func:`get <AbstractCorrelator.get>`, :func:`put <AbstractCorrelator.put>`,
    :func:`get <AbstractCorrelator.get_delivery>` and
    :func:`put <AbstractCorrelator.put_delivery>` methods.

    A Correlator is class that is used to store relations between SMPP requests and replies.
    Correlation is based on sequence number, and optionally message type,
    though running out of sequence numbers is normally not a concern.

    As a special case, SubmitSm requests are also correlated with DeliverSm delivery receipts.
    This correlation is based on message_id provided by SMSC.
    Delivery receipt may arrive days after sending, so this correlation should be persisted.

    User application provides log_id and optionally extra_data,
    which it can use for its own correlation.

    SubmitSm Correlation is based on message ID received in delivery report, which can
    either be in receipted_message_id optional parameter or in message text.
    '''

    # Parent MUST set these properties before use
    hook: AbstractHook = None  # type: ignore
    client_id: str = None  # type: ignore

    async def expired(self, smpp_message: SmppMessage) -> None:
        '''
        Correlator implementation MUST call this method whenever correlation data expires
        before receiving a response from SMPP peer.

        Parameters:
            smpp_message: Protocol message whose correlation data has expired.
        '''
        if isinstance(smpp_message, SubmitSm):
            await self.hook.send_error(smpp_message, _EXPIRED_ERROR, self.client_id)

    @abstractmethod
    async def put(self, smpp_message: SmppMessage) -> None:
        '''
        Called to store the correlation between a SMPP sequence number and sent message.

        Parameters:
            smpp_message: Protocol message that should be correlated.
        '''
        raise NotImplementedError()

    @abstractmethod
    async def put_delivery(self, smsc_message_id: str, log_id: str, extra_data: str) -> None:
        '''
        Called to store the correlation between a SubmitSm and a DeliverSm receipt.

        Parameters:
            smsc_message_id: Unique identifier of a message on the SMSC. It comes from SMSC.
            log_id: An ID that a user's application had previously supplied
                    to track/correlate different messages.
            extra_data: A string that a user's application had previously supplied
                           that it may want to be associated with the log_id.
        '''
        raise NotImplementedError()

    @abstractmethod
    async def get(self, smpp_command: SmppCommand, sequence_num: int) -> Optional[SmppMessage]:
        '''
        Called to get the correlation between a SMPP sequence number and sent message.

        Parameters:
            smpp_command: Any one of the SMSC commands eg submit_sm
            sequence_num: SMPP sequence_num

        Returns:
            Correlated Message object, if any
        '''
        raise NotImplementedError()

    @abstractmethod
    async def get_delivery(self, smsc_message_id: str) -> Tuple[str, str]:
        '''
        Called to get the correlation between a SubmitSm and a DeliverSm receipt.

        Parameters:
            smsc_message_id: Unique identifier of a message on the SMSC. It comes from SMSC.

        Returns:
            log_id and extra_data
        '''
        raise NotImplementedError()


class SimpleCorrelator(AbstractCorrelator):
    '''
    A simple implementation of AbstractCorrelator.
    It manages the correlation between SMPP requests and responses, and also between
    SubmitSM requests and DeliverSm receipts.
    WARNING: Not suitable for production!
             Correlation between SubmitSm and DeliverSM should be persisted.

    SimpleCorrelator also features an auto-expiration of dictionary items based on time.

    The storage is done in memory using a python dictionary. The storage looks like:

    .. highlight:: python
    .. code-block:: python

       {
            'sequence_num1': (681.109023565, EnquireLink()),
            'sequence_num1': (681.209023888, SubmitSm()),
            ...
       }
       {
            'smsc_message_id1': (681.109023565, 'log_id1', 'hook_metadata1'),
            'smsc_message_id2': (682.109023565, 'log_id2', 'hook_metadata2'),
            ...
       }
    '''

    def __init__(self, max_ttl: float = 15.00) -> None:
        '''
        Parameters:
            max_ttl: The time in seconds that an item is going to be stored.
                     After the expiration of max_ttl seconds, that item will be deleted.
        '''
        check_param(max_ttl, 'max_ttl', float)
        if max_ttl < 1.00:
            raise ValueError(f'Parameter max_ttl ({max_ttl}) must not be smaller than 1 second.')
        self.max_ttl: float = max_ttl
        self._store: Dict[int, Tuple[float, SmppMessage]] = {}
        self._delivery_store: Dict[str, Tuple[float, str, str]] = {}

    async def put(self, smpp_message: SmppMessage) -> None:
        await self._remove_expired()
        stored_at: float = time.monotonic()
        self._store[smpp_message.sequence_num] = (stored_at, smpp_message)

    async def put_delivery(self, smsc_message_id: str, log_id: str, extra_data: str) -> None:
        await self._remove_expired()
        stored_at: float = time.monotonic()
        self._delivery_store[smsc_message_id] = (stored_at, log_id, extra_data)

    async def get(self, smpp_command: SmppCommand, sequence_num: int) -> Optional[SmppMessage]:
        item: Optional[Tuple[float, SmppMessage]] = self._store.pop(sequence_num, None)
        await self._remove_expired()
        if not item:
            return None
        return item[1]

    async def get_delivery(self, smsc_message_id: str) -> Tuple[str, str]:
        item: Optional[Tuple[float, str, str]] = self._delivery_store.pop(smsc_message_id, None)
        await self._remove_expired()
        if not item:
            return '', ''
        return item[1], item[2]

    async def _remove_expired(self) -> None:
        '''
        Iterate over all stored items and delete any that are older than self.max_ttl seconds
        '''
        now: float = time.monotonic()
        sequence_num: int
        for sequence_num in tuple(self._store.keys()):
            stored_at: float
            message: SmppMessage
            stored_at, message = self._store[sequence_num]
            if now - stored_at > self.max_ttl:
                del self._store[sequence_num]
                await self.expired(message)

        if any(now - value[0] > self.max_ttl for value in self._delivery_store.values()):
            self._delivery_store = {
                key: value
                for key, value in self._delivery_store.items() if now - value[0] > self.max_ttl
            }
