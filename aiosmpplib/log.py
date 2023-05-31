import datetime
import time
import logging
from logging import (CRITICAL, DEBUG, ERROR, INFO, WARNING, Formatter, Handler, LogRecord, Logger, StreamHandler,
                     handlers)
from typing import Any, Deque, Dict, Optional, Union
from collections import deque
from .jsonutils import json_encode
from .utils import check_param

# def trace_to_root(message, *args, **kwargs):
#     logging.log(TRACE, message, *args, **kwargs)

TRACE: int = logging.DEBUG - 5
# Add TRACE level to logging module
logging.addLevelName(TRACE, 'TRACE')
setattr(logging, 'TRACE', TRACE)
# setattr(logging, 'trace', trace_to_root)


class StructuredLogger(Logger):
    '''
    It implements a structured logger that renders logs as JSON.

    example usage:

    .. highlight:: python
    .. code-block:: python

        logger = StructuredLogger('myLogger')
        logger.log(logging.INFO, event='web_request', url='https://www.google.com/')
    '''

    def __init__(self,
                 logger_name: str,
                 level: Union[str, int] = INFO,
                 log_metadata: Optional[Dict[str, Any]] = None,
                 handler: Optional[Handler] = None,
                 include_timestamp: bool = True,
                 include_level: bool = True) -> None:
        '''
        Parameters:
            logger_name: Name of the logger. It should be unique per logger.
            level: The level at which to log
            log_metadata: Metadata that will be included in all log statements
            handler: Python logging
                    `handler <https://docs.python.org/3/library/logging.html#logging.Handler>`_
                    to be attached to this logger. By default, `logging.StreamHandler` is used.
            include_timestamp: Whether to prefix log entries with datetime in ISO8601 format.
            include_level: Whether to prefix log entries with log level name.
        '''
        check_param(logger_name, 'logger_name', str)
        check_param(level, 'level', (int, str))
        check_param(log_metadata, 'log_metadata', dict, optional=True)
        check_param(handler, 'handler', Handler, optional=True)
        check_param(include_timestamp, 'include_timestamp', bool)
        check_param(include_level, 'include_level', bool)

        super().__init__(name=logger_name, level=self._check_level(level))
        self.log_metadata: dict = log_metadata or {}
        self.handler: Handler = handler or StreamHandler()
        self.include_timestamp: bool = include_timestamp
        self.include_level: bool = include_level

        self.handler.setFormatter(Formatter('%(message)s'))
        self.handler.setLevel(self.level)
        self.addHandler(self.handler)
        self.setLevel(self.level)

    def trace(self, msg: Any, *args, **kwargs):
        if self.isEnabledFor(TRACE):
            self._log(TRACE, msg, args, **kwargs)

    def debug(self, msg: Any, *args, **kwargs):
        if self.isEnabledFor(DEBUG):
            self._log(DEBUG, msg, args, **kwargs)

    def info(self, msg: Any, *args, **kwargs):
        if self.isEnabledFor(INFO):
            self._log(INFO, msg, args, **kwargs)

    def warning(self, msg: Any, *args, **kwargs):
        if self.isEnabledFor(WARNING):
            self._log(WARNING, msg, args, **kwargs)

    def error(self, msg: Any, *args, **kwargs):
        if self.isEnabledFor(ERROR):
            self._log(ERROR, msg, args, **kwargs)

    def exception(self, msg: Any, *args, exc_info: bool = True, **kwargs):
        self.error(msg, *args, exc_info=exc_info, **kwargs)

    def critical(self, msg: Any, *args, **kwargs):
        if self.isEnabledFor(CRITICAL):
            self._log(CRITICAL, msg, args, **kwargs)

    def log(self, level: int, msg: Any, *args, **kwargs):
        assert isinstance(level, int)
        if self.isEnabledFor(level):
            self._log(level, msg, args, **kwargs)

    def _log(self, level: int, msg: Any, *args, **kwargs):
        user_args: Dict = {
            key: value
            for key, value in kwargs.items() if key not in ('exc_info', 'extra', 'stack_info', 'stacklevel')
        }
        logger_args: Dict = {
            key: value
            for key, value in kwargs.items() if key in ('exc_info', 'extra', 'stack_info', 'stacklevel')
        }
        if self.include_timestamp:
            user_args['timestamp'] = datetime.datetime.now().isoformat()
        if self.include_level:
            user_args['log_level'] = logging.getLevelName(level)
        new_msg: str = self._process_msg(msg, **user_args)
        return super()._log(level, new_msg, *args, **logger_args)

    @staticmethod
    def _check_level(level: Union[str, int]) -> int:
        if isinstance(level, str):
            level = logging.getLevelName(level.upper())
            if not isinstance(level, int):
                # Strangely, getLevelName returns string f'Level {level}' if level is unknown
                raise ValueError(f'Unknown logging {level}.')
        return level

    def _process_msg(self, msg: Any, **user_args) -> str:
        merged_args: Dict[str, Any] = {**user_args, **self.log_metadata}
        if merged_args:
            return f'{msg} >>> {self._to_json(merged_args)}'
        return msg

    def _to_json(self, input_msg: Dict) -> str:
        '''
        Tries to convert the input message to JSON and returns it.
        If it fails, it returns the error in string (not JSON) format.
        '''
        try:
            return json_encode(input_msg)
        except Exception as err:  # pylint: disable=broad-except
            return f'aiosmpplib.StructuredLogger error: {repr(err)}'


class BreachHandler(handlers.MemoryHandler):
    '''
    This is an implementation of `logging.Handler` that puts logs in an in-memory ring buffer.
    When a trigger condition(eg a certain log level) is met;
    then all the logs in the buffer are flushed into a given stream(file, stdout etc)

    It is a bit like
    `logging.handlers.MemoryHandler
     <https://docs.python.org/3/library/logging.handlers.html#logging.handlers.MemoryHandler>`_
    except that it does not flush when the ring-buffer capacity is met
    but only when/if the trigger is met.

    It is inspired by the article
    `Triggering Diagnostic Logging on Exception
     <https://tersesystems.com/blog/2019/07/28/triggering-diagnostic-logging-on-exception/>`_

    example usage:

    .. highlight:: python
    .. code-block:: python

        import aiosmpplib, logging

        _handler = aiosmpplib.log.BreachHandler()
        logger = aiosmpplib.log.StructuredLogger('aha', handler=_handler, log_metadata={'id': '1'})

        logger.log(logging.INFO, {'name': 'Jayz'})
        logger.log(logging.ERROR, {'msg': 'Houston, we got 99 problems.'})

        # or alternatively, to use it with python stdlib logger
        logger = logging.getLogger('my-logger')
        handler = aiosmpplib.log.BreachHandler()
        formatter = logging.Formatter('%(message)s')
        handler.setFormatter(formatter)
        handler.setLevel('DEBUG')
        if not logger.handlers:
            logger.addHandler(handler)
        logger.setLevel('DEBUG')

        logger.info('I did records for Tweet before y'all could even tweet - Dr. Missy Elliot')
        logger.error('damn')
    '''

    def __init__(self,
                 flushLevel: int = WARNING,
                 capacity: int = 1000,
                 target: Optional[Handler] = None,
                 flushOnClose: bool = False,
                 heartbeatInterval: Optional[float] = None,
                 targetLevel: str = 'DEBUG') -> None:
        '''
        Parameters:
            flushLevel: the log level that will trigger this handler to
                        flush logs to :py:attr:`~target`
            capacity: the maximum number of log records to store in the ring buffer
            target: `log handler <https://docs.python.org/3/library/logging.html#logging.Handler>`_
                    that will be used.
            flushOnClose: whether to flush the buffer when the handler is closed
                          even if the flush level hasn't been exceeded
            heartbeatInterval: can be a float or None. If it is a float, then a heartbeat log
                               record will be emitted every :py:attr:`~heartbeatInterval` seconds.
                               If it is None (default), then no heartbeat log record is emitted.
                               If you decide to set it, a good value is at least 1800 (30 minutes).
            targetLevel: the log level to be applied/set to :py:attr:`~target`
        '''

        check_param(flushLevel, 'flushLevel', int)
        check_param(capacity, 'capacity', int)
        check_param(target, 'target', Handler, optional=True)
        check_param(flushOnClose, 'flushOnClose', bool)
        check_param(heartbeatInterval, 'heartbeatInterval', float, optional=True)
        check_param(targetLevel, 'targetLevel', str)
        if target is None:
            target = StreamHandler()

        # call `logging.handlers.MemoryHandler` init
        super().__init__(
            capacity=capacity,
            flushLevel=flushLevel,
            target=target,
            flushOnClose=flushOnClose,
        )

        # assuming each log record is 250 bytes, then the maximum
        # memory used by `buffer` will always be == 250*1_000/(1000*1000) == 0.25MB
        self.buffer: Deque[logging.LogRecord] = deque(maxlen=self.capacity)

        self.heartbeatInterval = heartbeatInterval
        if self.heartbeatInterval:
            self.heartbeatInterval = heartbeatInterval  # seconds
            self._s_time = time.monotonic()

        self.targetLevel: int = StructuredLogger._check_level(targetLevel)
        assert self.target is not None  # For type checkers
        self.target.setLevel(self.targetLevel)

    def shouldFlush(self, record: LogRecord) -> bool:
        '''
        Check for record at the flushLevel or higher.
        Implementation is mostly taken from `logging.handlers.MemoryHandler`
        '''
        return record.levelno >= self.flushLevel  # type: ignore # pytype: disable=attribute-error

    def emit(self, record: LogRecord) -> None:
        '''
        Emit a record.
        Append the record. If shouldFlush() tells us to, call flush() to process
        the buffer.

        Implementation is taken from `logging.handlers.MemoryHandler`
        '''
        self._heartbeat()

        if record.levelno >= self.targetLevel:
            self.buffer.append(record)
        if self.shouldFlush(record):
            self.flush()

    def _heartbeat(self) -> None:
        if not self.heartbeatInterval:
            return

        # check if `heartbeatInterval` seconds have passed.
        # if they have, emit a heartbeat log record to the target handler
        _now = time.monotonic()
        _diff = _now - self._s_time
        if _diff >= self.heartbeatInterval:
            self._s_time = _now
            # see: https://docs.python.org/3/library/logging.html#logging.LogRecord
            record = logging.makeLogRecord({
                'level': INFO,
                'name': 'BreachHandler',
                'pathname': '.../aiosmpplib/aiosmpplib/log.py',
                'func': 'BreachHandler._heartbeat',
                'msg': {
                    'event': 'aiosmpplib.BreachHandler.heartbeat',
                    'heartbeatInterval': self.heartbeatInterval,
                },
            })
            self.target.emit(record=record)  # type: ignore # pytype: disable=attribute-error
