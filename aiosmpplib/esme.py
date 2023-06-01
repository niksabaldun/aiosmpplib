import os
import random
import asyncio
from asyncio import StreamReader, StreamWriter, Task, CancelledError, IncompleteReadError
from codecs import CodecInfo
from string import ascii_lowercase, digits
from typing import Any, Awaitable, Callable, Dict, Optional, Set, Tuple, Type, TypeVar, Union
from .broker import AbstractBroker, SimpleBroker
from .correlator import AbstractCorrelator, SimpleCorrelator
from .hook import AbstractHook, SimpleHook
from .log import ERROR, WARNING, INFO, StructuredLogger, Handler
from .protocol import (DEFAULT_ENCODING, MESSAGE_TYPE_MAP, PDU_HEADER_LENGTH, SMPP_VERSION_3_4, SmppMessage,
                       GenericNack, SubmitSm, SubmitSmResp, DeliverSm, BindReceiver, BindTransmitter, BindTransceiver,
                       EnquireLink, Unbind)
from .ratelimiter import AbstractRateLimiter
from .retrytimer import AbstractRetryTimer, SimpleExponentialBackoff
from .sequence import AbstractSequenceGenerator, SimpleSequenceGenerator, assert_valid_sequence
from .throttle import AbstractThrottleHandler, SimpleThrottleHandler
from .state import (COMMAND_RESPONSE_MAP, RESPONSE_COMMAND_MAP, NPI, TON, PduHeader, BindMode, SmppCommand,
                    SmppDataCoding, SmppError, SmppSessionState, SmppCommandStatus)
from .utils import check_param

T = TypeVar('T')  # For generic type hints
# Maximum size of inbound network buffer.
# The message_payload parameter can hold up to 64k data, and we add a little more to that
# to guard against an unlikely possibility of LimitOverrunError.
_NETWORK_BUFFER_LIMIT = 2**16 + 1024


class ESME:
    '''
    The External Short Message Entities implementation that will interact with SMSC server.

    Example declaration:

    .. highlight:: Python
    .. code-block:: Python

        import os
        from aiosmpplib import ESME

        esme: ESME = ESME(
            smsc_host='127.0.0.1',
            smsc_port=2775,
            system_id='esme1',
            password=os.getenv('password', 'password'),
        )
        await esme.start()
    '''

    def __init__(
            self,
            smsc_host: str,
            smsc_port: int,
            system_id: str,
            password: str,
            system_type: str = '',
            addr_ton: TON = TON.UNKNOWN,
            addr_npi: NPI = NPI.UNKNOWN,
            address_range: str = '',
            bind_mode: BindMode = BindMode.TRANSCEIVER,
            # NON-SMPP ATTRIBUTES
            client_id: Optional[str] = None,
            enquire_link_interval: float = 55.00,
            log_level: Union[str, int] = INFO,
            log_metadata: Optional[Dict[str, Any]] = None,
            log_handler: Optional[Handler] = None,
            log_include_timestamp: bool = True,
            hook: Optional[AbstractHook] = None,
            broker: Optional[AbstractBroker] = None,
            rate_limiter: Optional[AbstractRateLimiter] = None,
            sequence_generator: Optional[AbstractSequenceGenerator] = None,
            throttle_handler: Optional[AbstractThrottleHandler] = None,
            correlator: Optional[AbstractCorrelator] = None,
            retry_timer: Optional[AbstractRetryTimer] = None,
            socket_timeout: float = 30.0,
            custom_codecs: Optional[Dict[str, CodecInfo]] = None,
            default_encoding: str = DEFAULT_ENCODING,
            testing: bool = False) -> None:
        '''
        Parameters:
            smsc_host: The IP address(or domain name) of the SMSC gateway/server
            smsc_port: The port at which SMSC is listening on
            system_id: Identifies the ESME system requesting to bind as
                       a transceiver with the SMSC.
            password: The password to be used by the SMSC to authenticate
                      the ESME requesting to bind.
            broker: A Python class instance implementing some queueing mechanism.
                    messages to be sent to SMSC are queued using the said mechanism before been sent
            client_id: A unique string identifying a aiosmpplib ESME class instance
            system_type: Identifies the type of ESME system requesting to bind with the SMSC.
            addr_ton: Type of Number of the ESME address.
            addr_npi: Numbering Plan Indicator (NPI) for ESME address(es) served
                      via this SMPP transceiver session
            address_range: A single ESME address or a range of ESME addresses served
                           via this SMPP transceiver session.
            bind_mode: ESME bind mode (transmitter, receiver, transceiver).
            enquire_link_interval: Time in seconds to wait before sending
                                   an enquire_link request to SMSC to check on its status
            log_level: The level at which to log
            log_metadata: Metadata that will be included in all log statements
            log_handler: Python logging handler to use for logging.
            log_include_timestamp: Whether to prefix log entries with datetime in ISO8601 format.
            hook: A AbstractHook instance implementing methods to be called
                  just before sending request to SMSC and just after getting response from SMSC
            rate_limiter: A AbstractRateLimiter instance implementing rate limitation
            sequence_generator: A AbstractSequenceGenerator instance used to generate sequence_nums
            throttle_handler: A AbstractThrottleHandler instance implementing logic for
                              dealing with throttled responses from SMSC
            correlator: A AbstractCorrelator instance used to store relations
                        between SMPP requests and responses, and also
                        between SubmitSM requests and DeliverSm receipts.
            retry_timer: A AbstractRetryTimer instance used to time reconnection retries.
            socket_timeout: Duration that ESME will wait, for socket/connection
                            related activities with SMSC, before timing out
            custom_codecs: A dictionary of encodings and their corresponding `codecs.CodecInfo
                           <https://docs.python.org/3/library/codecs.html#codecs.CodecInfo>`_
                           that you would like to register.
            default_encoding: SMSC default alphabet (SMPP 3.4 specification does not
                              enforce default alphabet, so it may be anything)
            testing: Set to True when doing unit tests

        Raises:
            ValueError: raised if there's an error instantiating a ESME.
        '''
        check_param(smsc_host, 'smsc_host', str)
        check_param(smsc_port, 'smsc_port', int)
        check_param(system_id, 'system_id', str, maxlen=15)
        check_param(password, 'password', str, maxlen=8)
        check_param(system_type, 'system_type', str, maxlen=12)
        check_param(addr_ton, 'addr_ton', TON)
        check_param(addr_npi, 'addr_npi', NPI)
        check_param(address_range, 'address_range', str, maxlen=40)
        check_param(bind_mode, 'bind_mode', BindMode)
        check_param(client_id, 'client_id', str, optional=True)
        check_param(enquire_link_interval, 'enquire_link_interval', float)
        check_param(log_level, 'log_level', (int, str))
        check_param(log_metadata, 'log_metadata', dict, optional=True)
        check_param(log_handler, 'log_handler', Handler, optional=True)
        check_param(log_include_timestamp, 'log_include_timestamp', bool)
        check_param(hook, 'hook', AbstractHook, optional=True)
        check_param(broker, 'broker', AbstractBroker, optional=True)
        check_param(rate_limiter, 'rate_limiter', AbstractRateLimiter, optional=True)
        check_param(sequence_generator, 'sequence_generator', AbstractSequenceGenerator, optional=True)
        check_param(throttle_handler, 'throttle_handler', AbstractThrottleHandler, optional=True)
        check_param(correlator, 'correlator', AbstractCorrelator, optional=True)
        check_param(retry_timer, 'retry_timer', AbstractRetryTimer, optional=True)
        check_param(socket_timeout, 'socket_timeout', float)
        check_param(custom_codecs, 'custom_codecs', dict, optional=True)
        check_param(default_encoding, 'default_encoding', str)
        check_param(testing, 'testing', bool)
        if default_encoding not in SmppDataCoding.__members__:
            raise ValueError(f'Unrecognised default SMPP encoding: `{default_encoding}`.')
        if custom_codecs:
            for _encoding, _codec_info in custom_codecs.items():
                if not isinstance(_codec_info, CodecInfo):
                    raise ValueError('`custom_codecs` should be a dictionary of encoding(string) '
                                     'to `codecs.CodecInfo`')
                if _encoding != _codec_info.name:
                    raise ValueError(f'The key `{_encoding}` must be equal to '
                                     f'codec name `{_codec_info.name}`')
                if _encoding not in SmppDataCoding.__members__:
                    raise ValueError(f'Unrecognised SMPP encoding: `{_encoding}`.')

        self.smsc_host: str = smsc_host
        self.smsc_port: int = smsc_port
        self.system_id: str = system_id
        self.password: str = password
        self.system_type: str = system_type
        self.addr_ton: TON = addr_ton
        self.addr_npi: NPI = addr_npi
        self.address_range: str = address_range
        self.bind_mode: BindMode = bind_mode
        self.client_id: str = client_id or ''.join(random.choices(ascii_lowercase + digits, k=17))
        self.enquire_link_interval: float = enquire_link_interval
        self.default_encoding: str = default_encoding
        self.custom_codecs: Optional[Dict[str, CodecInfo]] = custom_codecs
        self.testing: bool = testing
        if log_metadata is None:
            log_metadata = {
                'smsc_host': smsc_host,
                'system_id': system_id,
                'client_id': self.client_id,
                'pid': os.getpid(),
            }
        self._logger: StructuredLogger = StructuredLogger('esme' + self.client_id, log_level, log_metadata,
                                                          log_handler, log_include_timestamp)
        self.hook: AbstractHook = hook or SimpleHook(logger=self._logger)
        self.broker: AbstractBroker = broker or SimpleBroker()
        self.rate_limiter: Optional[AbstractRateLimiter] = rate_limiter
        self.sequence_generator: AbstractSequenceGenerator = (sequence_generator or SimpleSequenceGenerator())
        self.throttle_handler: AbstractThrottleHandler = (throttle_handler
                                                          or SimpleThrottleHandler(logger=self._logger))
        self.correlator: AbstractCorrelator = correlator or SimpleCorrelator()
        self.correlator.hook = self.hook
        self.correlator.client_id = self.client_id
        self.retry_timer: AbstractRetryTimer = retry_timer or SimpleExponentialBackoff()
        self.socket_timeout: float = socket_timeout
        self.interface_version: int = SMPP_VERSION_3_4
        self._session_state: SmppSessionState = SmppSessionState.CLOSED
        self._reader: Optional[StreamReader] = None
        self._writer: Optional[StreamWriter] = None
        self._is_shutting_down: bool = False
        self._drain_lock: asyncio.Lock = asyncio.Lock()
        self._data_received: asyncio.Event = asyncio.Event()
        self._bound: asyncio.Event = asyncio.Event()
        self._shut_down: asyncio.Event = asyncio.Event()

    async def _end_task(self, task: Task) -> None:
        '''
        Ends a top-level task after error or shutdown
        '''
        task_name: str = task.get_name()
        self._logger.debug('Ending task', task=task_name)
        try:
            await asyncio.wait_for(task, 0.5)  # Give task a chance to end gracefully
        except asyncio.TimeoutError:
            await self._cancel_task(task, task_name)
            return
        except (ConnectionError, TimeoutError, IncompleteReadError, OSError, ValueError):
            # We are ending a task so we don't care about errors
            pass
        self._logger.debug('Ended task', task=task_name)

    async def _cancel_task(self, task: Optional[Task], task_name: str) -> bool:
        '''
        Cancels an asyncio task
        '''
        if not task:
            task = next((t for t in asyncio.all_tasks() if t.get_name() == task_name), None)
        if not task or task.done():
            return False

        task.cancel()
        try:
            await task  # Will raise CancelledError
        except CancelledError:
            pass
        except RuntimeError:
            # If the coroutine sleeps, Runtime error "await wasn't used with future" will be raised
            pass
        except Exception:  # pylint: disable=broad-except
            self._logger.exception('Error while cancelling task.', task=task_name)

        return True

    async def _socket_operation(self, coro: Awaitable[T]) -> T:
        '''
        Performs network socket operation with timeout
        '''
        return await asyncio.wait_for(coro, self.socket_timeout)

    async def _get_pdu(self) -> Tuple[bytes, PduHeader]:
        '''
        Retrieves next PDU from SMSC
        '''
        assert isinstance(self._reader, StreamReader)  # For type checkers
        header_data: bytes = await self._reader.readexactly(PDU_HEADER_LENGTH)
        try:
            header: PduHeader = SmppMessage.parse_header(header_data)
        except ValueError:
            self._logger.exception('PDU header parse error', header=header_data.hex())
            raise
        body_data: bytes = await self._reader.readexactly(header.pdu_length - PDU_HEADER_LENGTH)
        return header_data + body_data, header

    async def _connection_keeper(self) -> None:
        '''
        Keeps TCP connection to server alive, and exits in case of broken connection.
        '''
        sleep_task: Optional[Task] = None
        event_task: Optional[Task] = None
        try:
            while True:
                # Wait for interval to expire or data event to be triggered, whichever comes first.
                # Receiver function will trigger the event after data is received.
                sleep_task = asyncio.create_task(asyncio.sleep(self.enquire_link_interval))
                event_task = asyncio.create_task(self._data_received.wait())
                done: Set[Task]
                done, _pending = await asyncio.wait({sleep_task, event_task}, return_when=asyncio.FIRST_COMPLETED)
                await next(iter(done))  # There must be only one element

                if self._is_shutting_down or self._session_state != self.bind_mode.session_state:
                    break

                if sleep_task in done:
                    # Interval expired, send keep-alive message
                    asyncio.create_task(self._send_data(EnquireLink()))
                    # Wait for data for predefined time, after which TimeoutError will be raised
                    await asyncio.wait_for(event_task, self.socket_timeout)
                else:
                    # Data was received, cancel sleep task and start over
                    await self._cancel_task(sleep_task, 'Connection keeper sleep')

                if self._is_shutting_down or self._session_state != self.bind_mode.session_state:
                    break

                self._data_received.clear()
        except asyncio.TimeoutError:
            # This error is expected so we don't include it in logging
            self._logger.error('Timed out while waiting for ENQUIRE_LINK response')
        except CancelledError:
            await self._cancel_task(sleep_task, 'Connection keeper sleep')
            await self._cancel_task(event_task, 'Connection keeper data wait')
            self._logger.debug('Connection keeper cancelled')
            raise

    async def _send_data(self, smpp_message: SmppMessage) -> None:
        '''
        Sends PDU's to SMSC over a network connection.
        This method does not block;
        it buffers the data and arranges for it to be sent out asynchronously.
        It also acts as a flow control method that interacts with the IO write buffer.

        Parameters:
            smpp_message: Message to be sent
        '''
        # TODO: Look at `set_write_buffer_limits` and `get_write_buffer_limits` methods
        # print('get_write_buffer_limits:', writer.transport.get_write_buffer_limits())

        self._logger.debug('Requested sending SMPP message', smpp_command=smpp_message.smpp_command.name)

        # Only bind-type commands can be sent in open state.
        # Otherwise, wait until we are in bound state.
        if not isinstance(smpp_message, (BindTransmitter, BindReceiver, BindTransceiver)):
            await self._bound.wait()

        if smpp_message.smpp_command in COMMAND_RESPONSE_MAP:
            # This is a request. A new sequence number must be generated,
            # and message saved for correlation with a response.
            sequence_num: int = self.sequence_generator.next_sequence()
            assert_valid_sequence(sequence_num)
            smpp_message.sequence_num = sequence_num

        self._logger.debug('Sending SMPP message',
                           smpp_command=smpp_message.smpp_command.name,
                           sequence_num=smpp_message.sequence_num)

        pdu: bytes = smpp_message.pdu()
        await self.hook.sending(smpp_message, pdu, self.client_id)  # Call user's hook

        # We use writer.drain() which is a flow control method that interacts with the
        # IO write buffer. When the size of the buffer reaches the high watermark,
        # drain blocks until the size of the buffer is drained down to the low watermark
        # and writing can be resumed.
        # When there is nothing to wait for, the drain() returns immediately.
        # ref: https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamWriter.drain
        assert isinstance(self._writer, StreamWriter)  # For type checkers
        self._writer.write(pdu)
        async with self._drain_lock:
            # see: https://github.com/komuw/naz/issues/114
            await self._writer.drain()

        self._logger.debug('Sent SMPP message',
                           smpp_command=smpp_message.smpp_command.name,
                           sequence_num=smpp_message.sequence_num)

        if smpp_message.smpp_command in COMMAND_RESPONSE_MAP:
            # If no error occured, save correlation data
            self._logger.debug('Saving request correlation data',
                               smpp_command=smpp_message.smpp_command,
                               sequence_num=smpp_message.sequence_num)
            await self.correlator.put(smpp_message)

    async def _dequeue_messages(self) -> Dict:
        '''
        In a loop; dequeues items from the :attr:`broker <ESME.broker>` and sends them to SMSC.
        '''
        try:
            while True:
                if self._is_shutting_down or self._session_state != self.bind_mode.session_state:
                    self._logger.info('Exiting dequeue loop due to broken connection')
                    return {'reason': 'shutdown'}

                self._logger.debug('Dequeue cycle start')

                # Check with throttle handler
                can_send: bool = await self.throttle_handler.allow_request()
                if can_send:
                    # Rate limit ourselves
                    if self.rate_limiter:
                        await self.rate_limiter.limit()
                    # Broker must never raise exception when dequeueing.
                    # It must handle exceptions internally and implement retry mechanism.
                    smpp_message: SmppMessage = await self.broker.dequeue()
                    if self.bind_mode == BindMode.RECEIVER:
                        if self._logger.isEnabledFor(WARNING):
                            self._logger.warning('ESME bound as receiver. Message discarded.', message=smpp_message)
                        continue
                    if isinstance(smpp_message, SubmitSm):
                        smpp_message.set_encoding_info(self.default_encoding, self.custom_codecs)
                    try:
                        await self._send_data(smpp_message)
                    except Exception as err:  # pylint: disable=broad-except
                        # We must intercept this exception to inform user application about failure
                        if self._logger.isEnabledFor(ERROR):
                            self._logger.exception('SMPP message could not be sent', message=smpp_message)
                        if isinstance(smpp_message, SubmitSm):
                            await self.hook.send_error(smpp_message, err, self.client_id)
                        # ValueError indicates problem with building the PDU, which is likely the
                        # result of invalid parameters passed by user application.
                        # Otherwise, it is a transport error and we must stop.
                        if not isinstance(err, ValueError):
                            raise

                    if self.testing:
                        # Offer escape hatch for tests to come out of endless loop
                        return smpp_message.__dict__
                else:
                    # Throttle_handler didn't allow us to send request.
                    delay: float = await self.throttle_handler.throttle_delay()
                    self._logger.debug('Sleeping due to denial by throttle handler', delay=delay)
                    await asyncio.sleep(delay)
                    if self.testing:
                        # Offer escape hatch for tests to come out of endless loop
                        return {'reason': 'throttle_handler_denied_request'}
        except CancelledError:
            self._logger.debug('Sender cancelled')
            raise

    async def _receive_data(self) -> Optional[bytes]:
        '''
        In a loop; read bytes from the network connected to SMSC and hand them over
        to the appropriate method for parsing.
        '''
        try:
            while True:
                if self._is_shutting_down or self._session_state != self.bind_mode.session_state:
                    self._logger.info('Exiting receive data loop due to broken connection')
                    return None

                self._logger.debug('Receive data cycle start')

                pdu: bytes
                header: PduHeader
                pdu, header = await self._get_pdu()
                self._data_received.set()  # Inform connection keeper that data was received
                pdu_handler: Callable[[bytes, PduHeader], Awaitable[Optional[SmppMessage]]]
                if header.smpp_command in COMMAND_RESPONSE_MAP:
                    pdu_handler = self._handle_request
                else:
                    pdu_handler = self._handle_response
                smpp_message: Optional[SmppMessage] = await pdu_handler(pdu, header)

                self._logger.debug('Calling user hook', hook_method='received')
                await self.hook.received(smpp_message, pdu, self.client_id)

                if header.smpp_command in COMMAND_RESPONSE_MAP:
                    # This is a request, we need to respond
                    response_command: SmppCommand = COMMAND_RESPONSE_MAP[header.smpp_command]
                    response_class: Type[SmppMessage] = MESSAGE_TYPE_MAP[response_command]
                    response: SmppMessage = response_class(header.sequence_num)
                    await self._send_data(response)

                if self.testing:
                    # Offer escape hatch for tests to come out of endless loop
                    return pdu
                if header.smpp_command == SmppCommand.UNBIND:
                    # Drop connection and force a reconnect
                    self._logger.info('Got UNBIND request from SMSC, reconnecting')
                    return None
        except CancelledError:
            self._logger.debug('Receiver cancelled')
            raise

    async def _handle_response(self, pdu: bytes, header: PduHeader) -> Optional[SmppMessage]:
        '''
        Handles response received from SMSC

        Parameters:
            pdu: PDU in bytes that have been read from network
            header: PduHeader instance containing data parsed from PDU header
        '''
        self._logger.debug('Handling SMPP response', header=header)

        if header.smpp_command not in (SmppCommand.BIND_TRANSMITTER_RESP, SmppCommand.BIND_RECEIVER_RESP,
                                       SmppCommand.BIND_TRANSCEIVER_RESP, SmppCommand.UNBIND_RESP,
                                       SmppCommand.SUBMIT_SM_RESP, SmppCommand.ENQUIRE_LINK_RESP,
                                       SmppCommand.GENERIC_NACK):
            # This should not happen; we don't send any other requests
            self._logger.warning('Received unexpected SMPP response', header=header)
            return None

        original_command: Optional[SmppCommand] = RESPONSE_COMMAND_MAP[header.smpp_command]
        original_message: Optional[SmppMessage] = await self.correlator.get(original_command, header.sequence_num)
        if not original_message:
            # This should not happen
            self._logger.error('Could not correlate SMPP response', header=header)
        elif (header.smpp_command != SmppCommand.GENERIC_NACK and original_message.smpp_command != original_command):
            # This should DEFINITELY not happen
            if self._logger.isEnabledFor(ERROR):
                self._logger.error('SMPP response correlated to unrelated request',
                                   header=header,
                                   request=original_message.__dict__)
            return None

        message_class: Type[SmppMessage] = MESSAGE_TYPE_MAP[header.smpp_command]
        try:
            smpp_message: SmppMessage = message_class.from_pdu(pdu, header)
        except ValueError:
            if self._logger.isEnabledFor(ERROR):
                self._logger.exception('Unable to parse PDU', header=header, pdu=pdu.hex())
            return None
        self._logger.debug('SMPP response parsed successfully', header=header)

        if isinstance(smpp_message, SubmitSmResp) and isinstance(original_message, SubmitSm):
            # Call throttling handler
            if header.command_status in (SmppCommandStatus.ESME_RTHROTTLED, SmppCommandStatus.ESME_RMSGQFUL):
                await self.throttle_handler.throttled()
            else:
                await self.throttle_handler.not_throttled()

            # Response may be SubmitSmResp or GenericNack
            smpp_message.log_id = original_message.log_id
            smpp_message.extra_data = original_message.extra_data
            if (isinstance(smpp_message, SubmitSmResp) and header.command_status == SmppCommandStatus.ESME_ROK):
                # The body of this only has `message_id` which is a C-Octet String
                # of variable length up to 65 octets.  It may be used at a later stage
                # to query the status of a message, cancel or replace the message.
                # Take the full message body minus terminating NULL char
                message_id_data: bytes = pdu[PDU_HEADER_LENGTH:header.pdu_length - 1]
                smsc_message_id: str = message_id_data.decode('ascii')
                self._logger.debug('Saving delivery receipt correlation data',
                                   smsc_message_id=smsc_message_id,
                                   log_id=original_message.log_id,
                                   extra_data=original_message.extra_data)
                await self.correlator.put_delivery(
                    smsc_message_id=smsc_message_id,
                    log_id=original_message.log_id,
                    extra_data=original_message.extra_data,
                )

        self._logger.debug('Handled SMPP response', header=header)

        return smpp_message

    async def _handle_request(self, pdu: bytes, header: PduHeader) -> Optional[SmppMessage]:
        '''
        Handles request received from SMSC

        Parameters:
            pdu: PDU in bytes that have been read from network
            header: PduHeader instance containing data parsed from PDU header
        '''
        self._logger.debug('Handling SMPP request', header=header)

        if header.smpp_command not in (SmppCommand.UNBIND, SmppCommand.ENQUIRE_LINK, SmppCommand.DELIVER_SM):
            # This should not happen; we can't handle any other requests
            self._logger.warning('Received unexpected SMPP request', header=header)
            await self._send_data(GenericNack(header.sequence_num))
            return None

        message_class: Type[SmppMessage] = MESSAGE_TYPE_MAP[header.smpp_command]
        try:
            smpp_message: SmppMessage = message_class.from_pdu(pdu, header, self.default_encoding, self.custom_codecs)
        except ValueError:
            if self._logger.isEnabledFor(ERROR):
                self._logger.exception('Unable to parse PDU', header=header, pdu=pdu.hex())
            await self._send_data(GenericNack(header.sequence_num))
            return None
        if isinstance(smpp_message, DeliverSm) and smpp_message.is_receipt():
            receipt: Dict[str, Any] = smpp_message.parse_receipt()
            msg_id: str = receipt.get('id', '')
            if msg_id:
                log_id: str
                extra_data: str
                log_id, extra_data = await self.correlator.get_delivery(msg_id)
                smpp_message.log_id = log_id
                smpp_message.extra_data = extra_data
                if log_id:
                    self._logger.debug('Correlated delivery receipt to SubmitSm',
                                       smsc_message_id=msg_id,
                                       log_id=log_id,
                                       extra_data=extra_data)
                else:
                    self._logger.warning('Could not correlate delivery receipt to SubmitSm', smsc_message_id=msg_id)
            else:
                self._logger.warning('Could not get receipted message ID from delivery receipt',
                                     header=header,
                                     receipt=receipt)

        self._logger.debug('Handled SMPP request', header=header)
        return smpp_message

    async def _disconnect(self) -> None:
        '''
        Drop connection to SMSC.
        '''
        if self._writer is None:
            return  # Already disconnected
        self._logger.debug('Closing network connection to SMSC')
        try:
            # 1. Set buffers to 0
            # 2. Unbind
            # 3. Drain
            # 4. Close connection
            # `start` function will await all tasks and set state to closed before it exits
            # see: https://github.com/komuw/naz/issues/117
            self._writer.transport.set_write_buffer_limits(0)  # pytype: disable=attribute-error
            if self._session_state == self.bind_mode.session_state:
                await self._send_data(Unbind())
            async with self._drain_lock:
                await self._writer.drain()
            self._writer.write_eof()
            self._writer = None
        except (OSError, TimeoutError, asyncio.TimeoutError):
            self._logger.exception('Error while shutting down SMSC connection')
        self._logger.debug('Closed network connection to SMSC')

    async def connect(self) -> None:
        '''
        Open connection to SMSC and bind as a transceiver.
        '''
        if self._session_state == self.bind_mode.session_state:
            return
        self._logger.info('Initiating connection to SMSC')
        self._writer = None
        conn_func = asyncio.open_connection(self.smsc_host, self.smsc_port, limit=_NETWORK_BUFFER_LIMIT)
        self._reader, self._writer = await self._socket_operation(conn_func)
        self._session_state = SmppSessionState.OPEN
        self._logger.info('Connected to SMSC, trying to bind as a %s', self.bind_mode.description)
        bind_command: SmppCommand = self.bind_mode.smpp_command
        bind_request_cls: Type[SmppMessage] = MESSAGE_TYPE_MAP[bind_command]
        assert bind_request_cls in (BindTransmitter, BindReceiver, BindTransceiver)
        bind_request: SmppMessage = bind_request_cls(
            system_id=self.system_id,
            password=self.password,
            system_type=self.system_type,
            interface_version=self.interface_version,
            addr_ton=self.addr_ton,
            addr_npi=self.addr_npi,
            address_range=self.address_range,
        )
        await self._socket_operation(self._send_data(bind_request))
        # Wait for response. Comment from original library developer stated that sometimes
        # the SMSC does not send the response. However, that would imply SMSC bug and
        # this behavior will not be taken into account until confirmed.
        pdu: bytes
        header: PduHeader
        pdu, header = await self._socket_operation(self._get_pdu())
        expected_response_command = COMMAND_RESPONSE_MAP[bind_command]
        if header.smpp_command != expected_response_command:
            raise SmppError(header.smpp_command, header.command_status)
        bind_response_cls: Type[SmppMessage] = MESSAGE_TYPE_MAP[expected_response_command]
        await self.hook.received(bind_response_cls.from_pdu(pdu, header), pdu, self.client_id)
        # ESME_RALYBND means that we are already bound.
        # This should not happen, but we cover it just in case.
        if header.command_status not in (SmppCommandStatus.ESME_ROK, SmppCommandStatus.ESME_RALYBND):
            self._session_state = SmppSessionState.CLOSED
            raise SmppError(header.smpp_command, header.command_status)
        self._session_state = self.bind_mode.session_state
        self._logger.info('Bound to SMSC as a %s', self.bind_mode.description)

    async def start(self) -> None:
        '''
        Start the ESME. Open connection to SMSC and bind as a transceiver.
        '''
        self._logger.info('Starting ESME')
        error_message: str = ''
        conn_error: Optional[Exception]
        all_tasks: Set[Task] = set()
        while True:
            try:
                all_tasks.clear()
                self._logger.debug('SMSC connect cycle start')
                conn_error = None
                await self.connect()  # Will raise error if not successful
                self.retry_timer.reset()
                self._bound.set()  # Tell _send_data it can proceed
                # Wait until any task fails
                all_tasks: Set[Task] = {
                    asyncio.create_task(self._receive_data(), name='Receiver'),
                    asyncio.create_task(self._dequeue_messages(), name='Sender'),
                    asyncio.create_task(self._connection_keeper(), name='Connection keeper'),
                }
                done_tasks: Set[Task] = set()
                pending_tasks: Set[Task] = set()
                done_tasks, pending_tasks = await asyncio.wait(all_tasks, return_when=asyncio.FIRST_COMPLETED)
                self._session_state = SmppSessionState.CLOSED
                task: Task
                for task in done_tasks:
                    await self._end_task(task)
                for task in pending_tasks:
                    await self._end_task(task)
            except SmppError as err:
                error_message = (f'Error response received from SMSC: '
                                 f'{err.smpp_command.name}: {err.command_status.name}')
                conn_error = err
            except ConnectionError as err:
                error_message = 'Connection lost while connecting to SMSC'
                conn_error = err
            except (TimeoutError, asyncio.TimeoutError) as err:
                error_message = 'Timed out while connecting to SMSC'
                conn_error = err
            except (IncompleteReadError, OSError, ValueError) as err:
                error_message = 'Error while reading from SMSC'
                conn_error = err
            except CancelledError:
                self._logger.debug('ESME starter cancelled')
                self._bound.clear()
                self._session_state = SmppSessionState.CLOSED
                await self._disconnect()
                for task in all_tasks:
                    await self._end_task(task)
                self._shut_down.set()
                raise

            self._bound.clear()
            self._session_state = SmppSessionState.CLOSED
            self._logger.error(error_message, exception=repr(conn_error))
            if self._is_shutting_down:
                break
            if conn_error and self._logger.isEnabledFor(INFO):
                delay: float = self.retry_timer.next_delay()
                if delay > 0.0:
                    self._logger.info('Delaying next connect attempt by %s seconds', delay)
            await self.retry_timer.wait()

        self._logger.debug('ESME starter ended')
        self._shut_down.set()

    async def stop(self) -> None:
        '''
        Cleanly shutdown the ESME.
        '''
        self._logger.info('Shutting down ESME')
        self._is_shutting_down = True
        await self._disconnect()
        await self._shut_down.wait()
        self._logger.info('ESME is shut down')

    @property
    def session_state(self) -> SmppSessionState:
        return self._session_state
