import asyncio
from abc import ABC, abstractmethod
from functools import reduce
from itertools import repeat
from .utils import check_param


class AbstractRetryTimer(ABC):
    '''
    This is the interface that must be implemented to satisfy aiosmpplib retry timing.
    User implementations should inherit this class and implement the
    :func:`wait <AbstractRetryTimer.wait>`, :func:`reset <AbstractRetryTimer.reset>`
    and :func:`reset <AbstractRetryTimer.next_delay>` methods.

    This class is used for timing consecutive retries in case of failure.
    '''

    @abstractmethod
    async def wait(self) -> None:
        '''
        Wait for some time, based on timer algorithm.
        Returns number of seconds waited.
        '''
        raise NotImplementedError()

    @abstractmethod
    def reset(self) -> None:
        '''
        Reset the timer to default.
        '''
        raise NotImplementedError()

    @abstractmethod
    def next_delay(self) -> float:
        '''
        Returns the next delay time in seconds.
        '''
        raise NotImplementedError()


class SimpleExponentialBackoff(AbstractRetryTimer):
    '''
    This is an implementation of AbstractRetryTimer using simple truncated exponential backoff.
    Retry delay starts at the minimum and is doubled up to the maximum.
    '''

    def __init__(self, min_delay: int = 1000, max_increases: int = 5) -> None:
        '''
        Parameters:
            min_delay: Minimum (starting) delay in milliseconds.
            max_increases: Maximum times to double the initial (minimum) delay.
        '''
        check_param(min_delay, 'min_delay', int)
        check_param(max_increases, 'max_increases', int)
        if min_delay < 1:
            raise ValueError('Parameter `min_delay` must be larger than zero.')
        if max_increases < 0:
            raise ValueError('Parameter `max_increases` must not be negative.')

        self._min_delay: int = min_delay
        self._max_delay: int = reduce(int.__mul__, repeat(2, max_increases), min_delay)
        self._next_delay: int = 0

    async def wait(self) -> None:
        if self._next_delay == 0:
            self._next_delay = self._min_delay
            return
        await asyncio.sleep(self._next_delay / 1000)
        if self._next_delay < self._max_delay:
            self._next_delay *= 2

    def reset(self) -> None:
        self._next_delay = 0

    def next_delay(self) -> float:
        return self._next_delay / 1000
