import time
import asyncio
from abc import ABC, abstractmethod
from .log import StructuredLogger
from .utils import check_param


class AbstractRateLimiter(ABC):
    '''
    This is the interface that must be implemented to satisfy aiosmpplib rate limiting.
    User implementations should inherit this class and
    implement the :func:`limit <AbstractRateLimiter.limit>` method.

    It may be important to control the rate at which the ESME sends requests to the SMSC.
    aiosmpplib lets you do this, by allowing you to specify a custom rate limiter.
    '''

    @abstractmethod
    async def limit(self) -> None:
        '''
        rate limit sending of messages to SMSC.
        '''
        raise NotImplementedError()


class SimpleRateLimiter(AbstractRateLimiter):
    '''
    This is an implementation of AbstractRateLimiter.

    It does rate limiting using a
    `token bucket rate limiting algorithm <https://en.wikipedia.org/wiki/Token_bucket>`_

    example usage:

    .. highlight:: python
    .. code-block:: python

        rate_limiter = SimpleRateLimiter(send_rate=10)
        await rate_limiter.limit()
        send_messages()
    '''

    def __init__(self, logger: StructuredLogger, send_rate: float = 100000.00) -> None:
        '''
        Parameters:
            logger: A python `logger <https://docs.python.org/3/library/html#Logger>`_
                    instance to be used for logging
            send_rate: The maximum rate, in messages/second, at which messages can be sent to SMSC.
        '''
        check_param(logger, 'logger', StructuredLogger)
        check_param(send_rate, 'send_rate', float)

        self.logger: StructuredLogger = logger
        self.send_rate: float = send_rate
        self.max_tokens: float = self.send_rate
        self.tokens: float = self.max_tokens
        self.delay_for_tokens: float = 1.0
        self.updated_at: float = time.monotonic()

        self.messages_delivered: int = 0
        self.effective_send_rate: float = 0.00

    async def limit(self) -> None:
        self.logger.debug('Rate limiter checking if request should be delayed.')
        while self.tokens < 1:
            self._add_new_tokens()
            self.logger.debug(
                'Rate limiter delayed the request.',
                delay=self.delay_for_tokens,
                send_rate=self.send_rate,
                effective_send_rate=self.effective_send_rate,
            )
            # todo: sleep in an exponential manner up to a maximum then wrap around.
            await asyncio.sleep(self.delay_for_tokens)

        self.messages_delivered += 1
        self.tokens -= 1

    def _add_new_tokens(self) -> None:
        now: float = time.monotonic()
        time_since_update: float = now - self.updated_at
        self.effective_send_rate = self.messages_delivered / time_since_update
        new_tokens: float = time_since_update * self.send_rate
        if new_tokens > 1:
            self.tokens = min(self.tokens + new_tokens, self.max_tokens)
            self.updated_at = now
            self.messages_delivered = 0
