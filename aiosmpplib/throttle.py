import time
from abc import ABC, abstractmethod
from .log import StructuredLogger, DEBUG, WARNING
from .utils import check_param


class AbstractThrottleHandler(ABC):
    '''
    This is the interface that must be implemented to satisfy aiosmpplib throttle handling.
    User implementations should inherit this class and implement:
    :func:`throttled <AbstractThrottleHandler.throttled>`,
    :func:`not_throttled <AbstractThrottleHandler.not_throttled>`,
    :func:`allow_request <AbstractThrottleHandler.allow_request>` and
    :func:`throttle_delay <AbstractThrottleHandler.throttle_delay>` methods.

    When an SMPP client exceeds it's rate limit, or when the SMSC is under load or for other reason;
    The SMSC may decide to start throtlling requests from that particular client.
    When it does so, it replies to the client with a throttling status. Under such conditions,
    it is important for the client to start rate limiting itself.
    The way aiosmpplib implements this self imposed self-regulation is via Throttle Handlers.

    The methods in this class are also called when the SMSC is under load and is
    responding with `ESME_RMSGQFUL`(message queue full) responses
    '''

    @abstractmethod
    async def throttled(self) -> None:
        '''
        This method will be called everytime we get a throttling response from SMSC.
        '''
        raise NotImplementedError()

    @abstractmethod
    async def not_throttled(self) -> None:
        '''
        This method will be called everytime we get any response
        from SMSC that is not a throttling response.
        '''
        raise NotImplementedError()

    @abstractmethod
    async def allow_request(self) -> bool:
        '''
        This method will be called just before sending a request to SMSC.
        The response from this method will determine wether aiosmpplib will send the request or not.
        '''
        raise NotImplementedError()

    @abstractmethod
    async def throttle_delay(self) -> float:
        '''
        if the last :func:`allow_request <AbstractThrottleHandler.allow_request>` method call
        returned False(thus denying sending a request),
        aiosmpplib will call the throttle_delay method
        to determine how long in seconds to wait before calling allow_request again.
        '''
        raise NotImplementedError()


class SimpleThrottleHandler(AbstractThrottleHandler):
    '''
    This is an implementation of AbstractThrottleHandler.

    It works by:

    - calculating the percentage of responses from the SMSC that are THROTTLING(or ESME_RMSGQFUL).
    - if percentage goes above :attr:`deny_request_at <SimpleThrottleHandler.deny_request_at>` \
      percent AND total number of responses from SMSC is greater than \
      :attr:`sample_size <SimpleThrottleHandler.sample_size>` over \
      :attr:`sampling_period <SimpleThrottleHandler.sampling_period>` seconds
    - then deny making anymore requests to SMSC

    '''

    def __init__(self,
                 logger: StructuredLogger,
                 sampling_period: float = 180.00,
                 sample_size: float = 50.00,
                 deny_request_at: float = 1.00,
                 throttle_wait: float = 3.00) -> None:
        '''
        Parameters:
            logger: A StructuredLogger instance to be used for logging
            sampling_period: The duration in seconds over which we will calculate
                             the percentage of throttled responses.
            sample_size: The minimum number of responses we should have got from SMSC over
                         :sampling_period duration to enable us make a decision.
            deny_request_at: The percent of throtlled responses above which we will deny ESME
                             from sending more requests to SMSC.
            throttle_wait: The time in seconds to wait before calling allow_request after
                           the last allow_request that returned False.
        '''
        check_param(logger, 'logger', StructuredLogger)
        check_param(sampling_period, 'sampling_period', float)
        check_param(sample_size, 'sample_size', float)
        check_param(deny_request_at, 'deny_request_at', float)
        check_param(throttle_wait, 'throttle_wait', float)

        self.non_throttle_responses: int = 0
        self.throttle_responses: int = 0
        self.updated_at: float = time.monotonic()

        self.sampling_period: float = sampling_period
        self.sample_size: float = sample_size
        self.deny_request_at: float = deny_request_at
        self.throttle_wait: float = throttle_wait
        self.logger: StructuredLogger = logger

    @property
    def percent_throttles(self) -> float:
        total_smsc_responses: int = self.non_throttle_responses + self.throttle_responses
        if total_smsc_responses < self.sample_size:
            # We do not have enough data to make a decision, so assume happy case
            return 0.0
        return round((self.throttle_responses / (total_smsc_responses)) * 100, 2)

    async def allow_request(self) -> bool:
        self.logger.debug('Checking if request should be throttled.')
        # Calculate percentage of throttles before resetting
        # non_throttle_responses and throttle_responses
        current_percent_throttles: float = self.percent_throttles
        _throttle_responses: int = self.throttle_responses
        _non_throttle_responses: int = self.non_throttle_responses

        now: float = time.monotonic()
        time_since_update: float = now - self.updated_at
        if time_since_update > self.sampling_period:
            # We are only interested in percent throttles in buckets of self.sampling_period
            # seconds, so reset values after self.sampling_period seconds.
            self.non_throttle_responses = 0
            self.throttle_responses = 0
            self.updated_at = now
        allowed: bool = current_percent_throttles <= self.deny_request_at
        log_level: int = DEBUG if allowed else WARNING
        if self.logger.isEnabledFor(log_level):
            self.logger.log(
                log_level,
                'Throttle handler result:',
                result='allowed' if allowed else 'denied',
                percent_throttles=current_percent_throttles,
                throttle_responses=_throttle_responses,
                non_throttle_responses=_non_throttle_responses,
                sampling_period=self.sampling_period,
                sample_size=self.sample_size,
                deny_request_at=self.deny_request_at,
            )
        return allowed

    async def not_throttled(self) -> None:
        self.non_throttle_responses += 1

    async def throttled(self) -> None:
        self.throttle_responses += 1

    async def throttle_delay(self) -> float:
        # todo: sleep in an exponential manner up to a maximum then wrap around.
        return self.throttle_wait
