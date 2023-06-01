import asyncio
from abc import ABC, abstractmethod

from .utils import check_param
from .protocol import SmppMessage


class AbstractBroker(ABC):
    '''
    This is the interface that must be implemented to satisfy aiosmpplib broker.
    User implementations should inherit this class and implement the
    :func:`enqueue <AbstractBroker.enqueue>` and
    :func:`dequeue <AbstractBroker.dequeue>` methods.

    aiosmpplib calls an implementation of this class to dequeue messages.
    '''

    @abstractmethod
    async def enqueue(self, message: SmppMessage) -> None:
        '''
        enqueue/save an item.

        Parameters:
            message: The item to be enqueued/saved
                     The message is a `aiosmpplib.protocol.SmppMessage` class instance;
                     It is up to the broker implementation to check that the message is indeed
                     SmppMessage instance, and perform the serialization (if neccesary)
                     in order to be able to store it.
                     `aiosmpplib.protocol.Message` has a `to_json()` method that you can use to
                     serialize a `aiosmpplib.protocol.Message` class instance into json.
        '''
        raise NotImplementedError()

    @abstractmethod
    async def dequeue(self) -> SmppMessage:
        '''
        dequeue an item.

        Returns:
            Item that was dequeued.
            The item has to be returned as a `aiosmpplib.protocol.Message` class instance.
            It is up to the broker implementation to do the de-serialization (if neccesary).
            `aiosmpplib.protocol` module has a utility function
            :func:`json_to_Message <aiosmpplib.protocol.json_to_Message>` that you can use to
            de-serialize a json string into `aiosmpplib.protocol.Message` class instance.
        '''
        raise NotImplementedError()


class SimpleBroker(AbstractBroker):
    '''
    This is an in-memory implementation of AbstractBroker.

    WARNING: It should only be used for tests and demo purposes.
    '''

    def __init__(self, maxsize: int = 2500) -> None:
        '''
        Parameters:
            maxsize: the maximum number of items that can be put in the queue.
        '''
        check_param(maxsize, 'maxsize', int)
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=maxsize)

    async def enqueue(self, message: SmppMessage) -> None:
        if not isinstance(message, SmppMessage):
            raise ValueError('Only instances of SmppMessage class can be enqueued')
        await self.queue.put(message)

    async def dequeue(self) -> SmppMessage:
        return await self.queue.get()
