from __future__ import annotations
from abc import ABC, abstractmethod
from codecs import CodecInfo
from dataclasses import dataclass
from datetime import datetime, timedelta
from math import floor
from struct import pack, unpack_from
from typing import Any, Dict, List, Optional, Tuple, Type, Union

from .codec import find_codec_info
from .state import (NPI, TON, OptionalParam, OptionalTag, PhoneNumber, SmppCommand,
                    SmppCommandStatus, SmppDataCoding, PduHeader)
from .utils import check_param, FixedOffset


NULL = b'\x00'
PDU_HEADER_LENGTH: int = 16
SMPP_VERSION_3_4: int = 0x34
DEFAULT_ENCODING: str = 'gsm0338'


class Base(ABC):
    def __post_init__(self):
        # Intercept the __post_init__ calls so they aren't relayed to `object`
        pass


@dataclass
class Trackable(Base):
    '''
    Represents interface for a SMPP message that supports tracking.

    Parameters:
        log_id: A unique identifier of this request
        extra_data: A custom string associated with this request.
    '''
    log_id: str = ''
    extra_data: str = ''

    def __post_init__(self) -> None:
        check_param(self.log_id, 'log_id', str)
        check_param(self.extra_data, 'extra_data', str)
        super().__post_init__()


@dataclass
class SmppMessage(Base):
    '''
    Represents the SMPP protocol message.

    Parameters:
        sequence_num: SMPP sequence number (for requests, generated before sending)
        command_status: SMPP response status (only relevant for responses)
    '''
    sequence_num: int = 0
    command_status: SmppCommandStatus = SmppCommandStatus.ESME_ROK

    def __post_init__(self) -> None:
        check_param(self.sequence_num, 'sequence_num', int)
        check_param(self.command_status, 'command_status', SmppCommandStatus)
        super().__post_init__()

    @property
    @abstractmethod
    def smpp_command(self) -> SmppCommand:
        raise NotImplementedError()

    def pack_header(self, pdu_len: int) -> bytes:
        '''
        Returns message PDU header (packed to binary data)
        '''
        return pack('!IIII', pdu_len, self.smpp_command, self.command_status, self.sequence_num)

    @staticmethod
    def parse_header(header_data: bytes) -> PduHeader:
        # First 16 bytes always contain:
        # PDU length, command ID, status, and sequence number, 4 bytes each
        pdu_length: int = unpack_from('!I', header_data)[0]
        command_id: int = unpack_from('!I', header_data, 4)[0]
        command_status_id: int = unpack_from('!I', header_data, 8)[0]
        sequence_num: int = unpack_from('!I', header_data, 12)[0]
        return PduHeader(
            pdu_length=pdu_length,
            smpp_command=SmppCommand(command_id),
            command_status=SmppCommandStatus(command_status_id),
            sequence_num=sequence_num
        )

    def as_dict(self) -> Dict[str, Any]:
        '''
        Returns message representation as dictionary. Override if necessary.
        '''
        return {param: value for param, value in self.__dict__.items()
                if not param.startswith('_')}

    def pdu(self) -> bytes:
        '''
        Returns message representation as SMPP PDU (encoded to binary data)
        '''
        # Many messages have empty body, so this is a default
        return self.pack_header(PDU_HEADER_LENGTH)

    @classmethod
    def from_pdu(cls, pdu: bytes, header: PduHeader, default_encoding: str='',
                 custom_codecs: Optional[Dict[str, CodecInfo]]=None) -> 'SmppMessage':
        '''
        Creates SmppMessage object from data parsed from byte sequence.
        PDU header needs to be pre-parsed because it contains PDU length and command type.

        Parameters:
            pdu: PDU in bytes that have been read from network
            header: PduHeader instance containing data parsed from PDU header
            default_encoding: SMPP default encoding (only needed for DeliverSm)
            custom_codecs: User-defined codecs (only needed for DeliverSm)
        '''
        # pylint: disable=unused-argument
        # Many messages have empty body, so this is a default
        return cls(header.sequence_num, header.command_status)


@dataclass
class SubmitSm(Trackable, SmppMessage):
    '''
    Represents the submit_sm SMPP message type.

    Parameters:
        short_message: Message to send to SMSC
        source: The phone number/identifier of the message sender
        destination: The phone number/identifier of the message recipient
        service_type: Indicates the SMS Application service associated with the message
        esm_class: Indicates Message Mode & Message Type.
        protocol_id: Protocol Identifier. Network specific field.
        priority_flag: Designates the priority level of the message.
        schedule_delivery_time: Time at which the message delivery should be first attempted.
        validity_period: The validity period of this message.
        registered_delivery: Indicator to signify if an SMSC delivery receipt
                                or an SME acknowledgement is required.
        replace_if_present_flag: Flag indicating if submitted message should replace
                                    an existing message.
                            ('canned') short messages stored on the SMSC
        encoding: `encoding <https://docs.python.org/3/library/codecs.html#standard-encodings>`_
                    used to encode messages been sent to SMSC. The encoding should be one of
                    the encodings recognised by the SMPP specification. See section 5.2.19 of
                    SMPP spec. If you want to use your own custom codec implementation for an
                    encoding, make sure to pass it to
                    :py:attr:`aiosmpplib.ESME.custom_codecs <aiosmpplib.ESME.custom_codecs>`
        sm_default_msg_id: Indicates the short message to send from a list of predefined
        message_payload: Optional parameter message_payload, needs special handling
        optional_params: List of optional parameters, if any
        auto_message_payload: Automatically use message_payload if message
                                does not fit in short_message
        error_handling: same meaning as the `errors` argument to Python's
                        `encode <https://docs.python.org/3/library/codecs.html#codecs.encode>`_
                        method
    '''
    short_message: str = ''
    source: PhoneNumber = PhoneNumber('')
    destination: PhoneNumber = PhoneNumber('')
    service_type: str = 'CMT'
    esm_class: int = 0x00000000
    protocol_id: int = 0x00000000
    priority_flag:int = 0x00000000
    schedule_delivery_time: Optional[Union[datetime, timedelta]] = None
    validity_period: Optional[Union[datetime, timedelta]] = None
    registered_delivery: int = 0b00000001
    replace_if_present_flag: int = 0x00000000
    encoding: Optional[str] = None
    sm_default_msg_id: int = 0x00000000
    message_payload: str = ''
    optional_params: Optional[List[OptionalParam]] = None
    auto_message_payload: bool = True
    error_handling: str = 'strict'

    def __post_init__(self) -> None:
        check_param(self.short_message, 'short_message', str)
        check_param(self.source, 'source', PhoneNumber)
        check_param(self.destination, 'destination', PhoneNumber)
        check_param(self.service_type, 'service_type', str)
        check_param(self.esm_class, 'esm_class', int)
        check_param(self.protocol_id, 'protocol_id', int)
        check_param(self.priority_flag, 'priority_flag', int)
        check_param(self.schedule_delivery_time, 'schedule_delivery_time', (datetime, timedelta),
                    optional=True)
        check_param(self.validity_period, 'validity_period', (datetime, timedelta), optional=True)
        check_param(self.registered_delivery, 'registered_delivery', int)
        check_param(self.replace_if_present_flag, 'replace_if_present_flag', int)
        check_param(self.encoding, 'encoding', str, optional=True)
        check_param(self.sm_default_msg_id, 'sm_default_msg_id', int)
        check_param(self.message_payload, 'message_payload', str)
        check_param(self.optional_params, 'optional_params', list, optional=True)
        check_param(self.auto_message_payload, 'auto_message_payload', bool)
        check_param(self.error_handling, 'error_handling', str)

        if self.optional_params is None:
            self.optional_params = []

        for opt_param in self.optional_params:
            if not isinstance(opt_param, OptionalParam):
                raise ValueError('`optional_params` should be a list of OptionalParam objects')
            if opt_param.tag == OptionalTag.MESSAGE_PAYLOAD:
                raise ValueError('`OptionalTag.MESSAGE_PAYLOAD` cannot be included in '
                                 '`optional_params`. Use `message_payload` parameter instead.')

        if not self.short_message and not self.message_payload:
            raise ValueError('Either short_message or message_payload must be specified')
        if self.short_message and self.message_payload:
            raise ValueError('Specifying both short_message and message_payload is not allowed')
        if not self.destination.number:
            raise ValueError('Destination number must be specified')
        super().__post_init__()
        # default_encoding and custom_codecs need to be set by ESME/SMSC before sending
        self._default_encoding: str = DEFAULT_ENCODING
        self._custom_codecs: Optional[Dict[str, CodecInfo]] = None

    @property
    def smpp_command(self) -> SmppCommand:
        return SmppCommand.SUBMIT_SM

    @staticmethod
    def datetime_to_smpp_time(time_object: Optional[Union[datetime, timedelta]]) -> str:
        if time_object is None:
            return ''
        if isinstance(time_object, datetime):
            # datetime is converted to absolute validity
            tenth_second: str = str(time_object.microsecond // 100000)
            offset: Optional[timedelta] = (time_object.tzinfo.utcoffset(time_object)
                                           if time_object.tzinfo else None)
            offset_str: str
            prefix: str
            if not offset:
                offset_str = '00'
                prefix = '+'
            else:
                # Unit is quarter-hour (15 minutes)
                offset_str: str = f'{int(floor(offset.seconds / (60 * 15))):02d}'
                prefix: str = '-' if offset.days < 0 else '+'
            return time_object.strftime('%y%m%d%H%M%S') + tenth_second + offset_str + prefix
        if isinstance(time_object, timedelta):
            # timedelta is converted to relative validity
            if time_object > timedelta(weeks=63):
                raise ValueError('Maximum message validity is 63 weeks')
            two_digit_format: str = '{:02d}'
            total_days: int = time_object.days
            years: str = two_digit_format.format(total_days // 365)
            total_days %= 365
            months: str = two_digit_format.format(total_days // 30)
            days: str = two_digit_format.format(total_days % 30)
            total_seconds: int = time_object.seconds
            hours: str = two_digit_format.format(total_seconds // 3600)
            total_seconds %= 3600
            minutes: str = two_digit_format.format(total_seconds // 60)
            seconds: str = two_digit_format.format(total_seconds % 60)
            return years + months + days + hours + minutes + seconds + '000R'
        raise ValueError('Only datetime and timedelta objects can be converted to SMPP validity')

    @staticmethod
    def smpp_time_to_datetime(validity: str) -> Optional[Union[datetime, timedelta]]:
        if not validity:
            return None
        year: int = int(validity[0:2])
        month: int = int(validity[2:4])
        day: int = int(validity[4:6])
        hour: int = int(validity[6:8])
        minute: int = int(validity[8:10])
        second: int = int(validity[10:12])
        if validity.endswith('R'):
            # Relative validity, convert to timedelta
            # For simplicity, year = 365 days, month = 30 days
            total_days: int = year * 365 + month * 30 + day
            total_seconds: int = hour * 3600 + minute * 60 + second
            return timedelta(days=total_days, seconds=total_seconds)
        # Absolute validity, convert to datetime
        tenth_second: int = int(validity[12:13])
        offset_str: str = validity[15:16] + validity[13:15]
        offset: FixedOffset = FixedOffset.from_timezone(offset_str)
        return datetime(
            year=year,
            month=month,
            day=day,
            hour=hour,
            minute=minute,
            second=second,
            microsecond=tenth_second * 1000000,
            tzinfo=offset,
        )

    def set_encoding_info(self, default_encoding: str,
                          custom_codecs: Optional[Dict[str, CodecInfo]]) -> None:
        self._default_encoding = default_encoding
        self._custom_codecs = custom_codecs

    def smpp_encode(self, text: str) -> bytes:
        if not self.encoding:
            # Auto; first try default encoding, fallback to UCS2
            try:
                codec_info: CodecInfo = find_codec_info(self._default_encoding, self._custom_codecs)
                result: bytes = codec_info.encode(text, self.error_handling)[0]
            except UnicodeEncodeError:
                codec_info: CodecInfo = find_codec_info('ucs2', self._custom_codecs)
                result: bytes = codec_info.encode(text, self.error_handling)[0]
                self.encoding = 'ucs2'
        else:
            codec_info: CodecInfo = find_codec_info(self.encoding, self._custom_codecs)
            result: bytes = codec_info.encode(text, self.error_handling)[0]
        return result

    def pdu(self) -> bytes:
        # If encoding is set to auto, smpp_encode will set encoding param of the message
        # to ucs2 if default encoding cannot be used
        encoded_short_message: bytes = self.smpp_encode(self.short_message or self.message_payload)
        encoded_message_payload: bytes = b''
        if self.encoding:
            data_coding: int = SmppDataCoding[self.encoding].value
        else:
            data_coding: int = 0 # SMSC default
        sm_length: int = len(encoded_short_message)
        if sm_length > 254 and self.short_message and not self.auto_message_payload:
            # short_message supports up to 254 bytes, so this does not fit,
            # but automatic moving to message_payload was deactivated
            raise ValueError(f'Message is too long ({sm_length} bytes, maximum is 254)')
        if sm_length > 254 or self.message_payload:
            tag: int = OptionalTag.MESSAGE_PAYLOAD.value
            encoded_message_payload = pack('!HH', tag, sm_length) + encoded_short_message
            encoded_short_message = b''
            sm_length = 0

        body: bytes = (
            self.service_type.encode('ascii') + NULL
            + pack('!BB', self.source.ton, self.source.npi)
            + self.source.number.encode('ascii') + NULL
            + pack('!BB', self.destination.ton, self.destination.npi)
            + self.destination.number.encode('ascii') + NULL
            + pack('!BBB', self.esm_class, self.protocol_id, self.priority_flag)
            + self.datetime_to_smpp_time(self.schedule_delivery_time).encode('ascii') + NULL
            + self.datetime_to_smpp_time(self.validity_period).encode('ascii') + NULL
            + pack('!BB', self.registered_delivery, self.replace_if_present_flag)
            + pack('!BBB', data_coding, self.sm_default_msg_id, sm_length)
            + encoded_short_message
            + encoded_message_payload
            + b''.join(opt_param.tlv for opt_param in self.optional_params or [])
            # optional params may be included in ANY ORDER within
            # the `Optional Parameters` section of the SMPP PDU.
        )
        return self.pack_header(PDU_HEADER_LENGTH + len(body)) + body

    @classmethod
    def from_pdu(cls, pdu: bytes, header: PduHeader, default_encoding: str='',
                 custom_codecs: Optional[Dict[str, CodecInfo]]=None) -> SmppMessage:
        def get_c_octet_string() -> str:
            nonlocal index
            str_end: int = pdu.index(NULL, index)
            octet_string: str = pdu[index:str_end].decode('ascii')
            index = str_end + 1
            return octet_string

        def get_octet_string(count: int) -> str:
            nonlocal index
            octet_string: str = pdu[index:index+count].decode('ascii')
            if octet_string.endswith(chr(0)): # String may be null-terminated
                octet_string = octet_string[:-1]
            index += count
            return octet_string

        def get_integer(count: int) -> int:
            nonlocal index
            int_format: Dict[int, str] = {
                1: '!B', # unsigned char
                2: '!H', # unsigned short
                4: '!I', # unsigned int
            }
            integer: int = unpack_from(int_format[count], pdu, index)[0]
            index += count
            return integer

        index: int = PDU_HEADER_LENGTH # Only body is parsed here, header is pre-parsed
        service_type: str = get_c_octet_string()
        source_ton: TON = TON(get_integer(1))
        source_npi: NPI = NPI(get_integer(1))
        source: PhoneNumber = PhoneNumber(get_c_octet_string(), source_ton, source_npi)
        dest_ton: TON = TON(get_integer(1))
        dest_npi: NPI = NPI(get_integer(1))
        destination: PhoneNumber = PhoneNumber(get_c_octet_string(), dest_ton, dest_npi)
        esm_class: int = get_integer(1)
        protocol_id: int = get_integer(1)
        priority_flag: int = get_integer(1)
        schedule_delivery_time: str = get_c_octet_string()
        validity_period: str = get_c_octet_string()
        registered_delivery: int = get_integer(1)
        replace_if_present_flag: int = get_integer(1)
        data_coding: int = get_integer(1)
        if data_coding:
            encoding: str = SmppDataCoding(data_coding).name
        else:
            encoding: str = default_encoding
        codec_info: CodecInfo = find_codec_info(encoding, custom_codecs)
        sm_default_msg_id: int = get_integer(1)
        sm_length: int = get_integer(1)
        short_message: str = codec_info.decode(pdu[index:index+sm_length])[0]
        index += sm_length

        message_payload: str = ''
        # Read optional parameters, if any
        optional_params: List[OptionalParam] = []
        while index < header.pdu_length:
            tag: OptionalTag = OptionalTag(get_integer(2))
            length: int = get_integer(2)
            if tag == OptionalTag.MESSAGE_PAYLOAD:
                # message_payload is a special case, it is an alternative to short_message
                message_payload = codec_info.decode(pdu[index:index+length])[0]
                index += length
            elif tag.data_type == int:
                int_value: int = get_integer(length)
                optional_params.append(OptionalParam(tag, int_value))
            elif tag.data_type == bool:
                # alert_on_message_delivery doesn't have an actual value (it is zero-length),
                # but is a bool param, so we set it to True
                optional_params.append(OptionalParam(tag, True))
            else:
                # Only other possible type is str
                str_value: str = get_octet_string(length)
                optional_params.append(OptionalParam(tag, str_value))

        return cls(
            sequence_num=header.sequence_num,
            short_message=short_message,
            source=source,
            destination=destination,
            service_type=service_type,
            esm_class=esm_class,
            protocol_id=protocol_id,
            priority_flag=priority_flag,
            schedule_delivery_time=cls.smpp_time_to_datetime(schedule_delivery_time),
            validity_period=cls.smpp_time_to_datetime(validity_period),
            registered_delivery=registered_delivery,
            replace_if_present_flag=replace_if_present_flag,
            encoding=encoding if encoding != DEFAULT_ENCODING else None,
            sm_default_msg_id=sm_default_msg_id,
            message_payload=message_payload,
            optional_params=optional_params,
        )


@dataclass
class SubmitSmResp(Trackable, SmppMessage):
    '''
    Represents the submit_sm_resp SMPP message type.

    Parameters:
        message_id: Message ID assigned by the SMSC.
    '''
    message_id: str = ''

    def __post_init__(self) -> None:
        check_param(self.message_id, 'message_id', str)
        super().__post_init__()

    @property
    def smpp_command(self) -> SmppCommand:
        return SmppCommand.SUBMIT_SM_RESP

    def pdu(self) -> bytes:
        body: bytes = self.message_id.encode('ascii') + NULL
        return self.pack_header(PDU_HEADER_LENGTH + len(body)) + body

    @classmethod
    def from_pdu(cls, pdu: bytes, header: PduHeader, default_encoding: str='',
                 custom_codecs: Optional[Dict[str, CodecInfo]]=None) -> SmppMessage:
        # pylint: disable=unused-argument
        # Decode the full body of the PDU, minus terminating NULL char
        message_id: str = pdu[PDU_HEADER_LENGTH:header.pdu_length-1].decode('ascii')
        return cls(
            sequence_num=header.sequence_num,
            message_id=message_id,
            command_status=header.command_status,
        )


@dataclass
class DeliverSm(SubmitSm):
    '''
    Represents the deliver_sm SMPP message type.

    Parameters:
        receipt: A dictionary containing delivery receipt data
    '''
    receipt: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        check_param(self.receipt, 'receipt', dict, optional=True)
        receipt: Optional[Dict[str, Any]] = self.receipt
        if receipt:
            self.esm_class = 0b00000100
        if receipt and not self.short_message:
            # Encode receipt in short_message text
            # Receipt format is SMSC-specific, but it usually follows the following pattern
            msg_id: str = receipt.get('id', '') # Message ID allocated by the SMSC when submitted.
            sub: int = receipt.get('sub', 0) # Number of short messages originally submitted.
            dlvrd: int = receipt.get('dlvrd', 0) # Number of short messages delivered.
            # The time and date at which the message was submitted.
            submit_date: Optional[datetime] = receipt.get('submit date')
            submit_date_str: str = submit_date.strftime('%y%m%d%H%M') if submit_date else ''
            # The time and date at which the message reached its final state.
            done_date: Optional[datetime] = receipt.get('done date')
            done_date_str: str = done_date.strftime('%y%m%d%H%M') if done_date else ''
            stat: str = receipt.get('stat', '') # The final status of the message.
            err: str = receipt.get('err', '') # Network specific error code or an SMSC error code.
            text: str = receipt.get('text', '') # The first 20 characters of the short message.
            self.short_message = (f'id:{msg_id} sub:{sub:03d} dlvrd:{dlvrd:03d}'
                                  f' submit date:{submit_date_str} done date:{done_date_str}'
                                  f' stat:{stat} err:{err} Text:{text:20}')
        super().__post_init__()

    @property
    def smpp_command(self) -> SmppCommand:
        return SmppCommand.DELIVER_SM

    @classmethod
    def from_pdu(cls, pdu: bytes, header: PduHeader, default_encoding: str='',
                 custom_codecs: Optional[Dict[str, CodecInfo]]=None) -> SmppMessage:
        deliver_sm: SmppMessage = super().from_pdu(pdu, header, default_encoding, custom_codecs)
        assert isinstance(deliver_sm, DeliverSm) # For type checkers

        def get_receipt_param() -> Tuple[Optional[str], Optional[str]]:
            nonlocal index
            nonlocal deliver_sm
            str_end: int = deliver_sm.short_message.find(':', index)
            if str_end == -1:
                return None, None
            param: str = deliver_sm.short_message[index:str_end].lower()
            index = str_end + 1
            str_end = deliver_sm.short_message.find(' ', index)
            if str_end == -1 or param == 'text': # Text must be last
                str_end = len(deliver_sm.short_message)
            value: str = deliver_sm.short_message[index:str_end]
            index = str_end + 1
            return param, value

        # Only middle 4 bits are relevant: 0 = incoming SMS, 1 = delivery receipt
        message_class: int = (deliver_sm.esm_class & 0b00111100) >> 2
        if message_class == 1:
            # This is a delivery receipt
            rcpt_data: Dict = {}
            index = 0
            rcpt_param: Optional[str]
            rcpt_value: Optional[str]
            while True:
                rcpt_param, rcpt_value = get_receipt_param()
                if rcpt_param is None or rcpt_value is None:
                    break
                if rcpt_param in ('sub', 'dlvrd'):
                    rcpt_data[rcpt_param] = int(rcpt_value)
                elif rcpt_param in ('submit date', 'done date'):
                    rcpt_data[rcpt_param] = datetime.strptime(rcpt_value, '%y%m%d%H%M')
                elif rcpt_param in ('id', 'stat', 'err', 'text'):
                    rcpt_data[rcpt_param] = rcpt_value
                else:
                    rcpt_data[rcpt_param] = rcpt_value

            smsc_message_id: Optional[str] = rcpt_data.get('id') # Get message ID from report data
            if not smsc_message_id and deliver_sm.optional_params:
                # Message ID not found, check if receipted_message_id param exists
                id_param: Optional[OptionalParam] = next((
                    param for param in deliver_sm.optional_params
                    if param.tag == OptionalTag.RECEIPTED_MESSAGE_ID
                ), None)
                if id_param:
                    rcpt_data['id'] = id_param.value
            deliver_sm.receipt = rcpt_data

        return deliver_sm


@dataclass
class DeliverSmResp(SubmitSmResp):
    '''
    Represents the deliver_sm_resp SMPP message type.
    '''
    @property
    def smpp_command(self) -> SmppCommand:
        return SmppCommand.DELIVER_SM_RESP


@dataclass
class GenericNack(Trackable, SmppMessage):
    '''
    Represents the generic_nack SMPP message type.
    '''
    @property
    def smpp_command(self) -> SmppCommand:
        return SmppCommand.GENERIC_NACK


@dataclass
class BindTransceiver(SmppMessage):
    '''
    Represents the bind_transceiver SMPP message type.

    Parameters:
        system_id: Identifies the ESME system requesting to bind as a transceiver.
        password: Password used to authenticate the ESME requesting to bind.
        system_type: Identifies the type of ESME system requesting to bind as a transceiver.
        interface_version: Indicates the version of the SMPP protocol supported by the ESME.
        addr_ton: Type of Number for ESME address(es) served via this SMPP session.
        addr_npi: Numbering Plan Indicator for ESME address(es) served via this SMPP session.
        address_range: A single ESME address or a range of ESME addresses served via
                        this SMPP transceiver session.
    '''
    system_id: str = ''
    password: str = ''
    system_type: str = ''
    interface_version: int = SMPP_VERSION_3_4
    addr_ton: TON = TON.UNKNOWN
    addr_npi: NPI = NPI.UNKNOWN
    address_range: str = ''

    @property
    def smpp_command(self) -> SmppCommand:
        return SmppCommand.BIND_TRANSCEIVER

    def pdu(self) -> bytes:
        body: bytes = (
            self.system_id.encode('ascii') + NULL
            + self.password.encode('ascii') + NULL
            + self.system_type.encode('ascii') + NULL
            + pack('!BBB', self.interface_version, self.addr_ton, self.addr_npi)
            + self.address_range.encode('ascii') + NULL
        )
        return self.pack_header(PDU_HEADER_LENGTH + len(body)) + body

    @classmethod
    def from_pdu(cls, pdu: bytes, header: PduHeader, default_encoding: str='',
                 custom_codecs: Optional[Dict[str, CodecInfo]]=None) -> SmppMessage:
        # pylint: disable=unused-argument
        def get_c_octet_string() -> str:
            nonlocal index
            str_end: int = pdu.index(NULL, index)
            octet_string: str = pdu[index:str_end].decode('ascii')
            index = str_end + 1
            return octet_string

        def get_char() -> int:
            nonlocal index
            integer: int = unpack_from('!B', pdu, index)[0]
            index += 1
            return integer

        index: int = PDU_HEADER_LENGTH # Only body is parsed here, header is pre-parsed
        system_id: str = get_c_octet_string()
        password: str = get_c_octet_string()
        system_type: str = get_c_octet_string()
        interface_version: int = get_char()
        addr_ton: TON = TON(get_char())
        addr_npi: NPI = NPI(get_char())
        address_range: str = get_c_octet_string()

        return cls(
            sequence_num=header.sequence_num,
            system_id=system_id,
            password=password,
            system_type=system_type,
            interface_version=interface_version,
            addr_ton=addr_ton,
            addr_npi=addr_npi,
            address_range=address_range,
        )


@dataclass
class BindTransceiverResp(SmppMessage):
    '''
    Represents the bind_transceiver_resp SMPP message type.

    Parameters:
        system_id: SMSC system ID.
        sc_interface_version: Optional SMPP version supported by SMSC.
    '''
    system_id: str = ''
    sc_interface_version: Optional[int] = None

    @property
    def smpp_command(self) -> SmppCommand:
        return SmppCommand.BIND_TRANSCEIVER_RESP

    def pdu(self) -> bytes:
        body: bytes = self.system_id.encode('ascii') + NULL
        if self.sc_interface_version is not None:
            body += OptionalParam(OptionalTag.SC_INTERFACE_VERSION, self.sc_interface_version).tlv
        return self.pack_header(PDU_HEADER_LENGTH + len(body)) + body

    @classmethod
    def from_pdu(cls, pdu: bytes, header: PduHeader, default_encoding: str='',
                 custom_codecs: Optional[Dict[str, CodecInfo]]=None) -> SmppMessage:
        # pylint: disable=unused-argument
        index: int = pdu.index(NULL, PDU_HEADER_LENGTH)
        system_id: str = pdu[PDU_HEADER_LENGTH:index].decode('ascii')
        index += 1
        sc_interface_version: Optional[int] = None
        if index < header.pdu_length:
            # Optional param sc_interface_version. It must have a total of 5 bytes in length.
            index += 4
            if index + 1 == header.pdu_length:
                sc_interface_version = unpack_from('!B', pdu, index)[0]
        return cls(
            sequence_num=header.sequence_num,
            command_status=header.command_status,
            system_id=system_id,
            sc_interface_version=sc_interface_version,
        )


@dataclass
class BindTransmitter(BindTransceiver):
    '''
    Represents the bind_transmitter SMPP message type.
    '''
    @property
    def smpp_command(self) -> SmppCommand:
        return SmppCommand.BIND_TRANSMITTER


@dataclass
class BindTransmitterResp(BindTransceiverResp):
    '''
    Represents the bind_transmitter_resp SMPP message type.
    '''
    @property
    def smpp_command(self) -> SmppCommand:
        return SmppCommand.BIND_TRANSMITTER_RESP


@dataclass
class BindReceiver(BindTransceiver):
    '''
    Represents the bind_receiver SMPP message type.
    '''
    @property
    def smpp_command(self) -> SmppCommand:
        return SmppCommand.BIND_RECEIVER


@dataclass
class BindReceiverResp(BindTransceiverResp):
    '''
    Represents the bind_receiver_resp SMPP message type.
    '''
    @property
    def smpp_command(self) -> SmppCommand:
        return SmppCommand.BIND_RECEIVER_RESP


@dataclass
class EnquireLink(SmppMessage):
    '''
    Represents the enquire_link SMPP message type.
    '''
    @property
    def smpp_command(self) -> SmppCommand:
        return SmppCommand.ENQUIRE_LINK


@dataclass
class EnquireLinkResp(SmppMessage):
    '''
    Represents the enquire_link_resp SMPP message type.
    '''
    @property
    def smpp_command(self) -> SmppCommand:
        return SmppCommand.ENQUIRE_LINK_RESP


@dataclass
class Unbind(SmppMessage):
    '''
    Represents the unbind SMPP message type.
    '''
    @property
    def smpp_command(self) -> SmppCommand:
        return SmppCommand.UNBIND


@dataclass
class UnbindResp(SmppMessage):
    '''
    Represents the unbind_resp SMPP message type.
    '''
    @property
    def smpp_command(self) -> SmppCommand:
        return SmppCommand.UNBIND_RESP


MESSAGE_TYPE_MAP: Dict[SmppCommand, Type[SmppMessage]] = {
    SmppCommand.GENERIC_NACK: GenericNack,
    SmppCommand.SUBMIT_SM: SubmitSm,
    SmppCommand.SUBMIT_SM_RESP: SubmitSmResp,
    SmppCommand.DELIVER_SM: DeliverSm,
    SmppCommand.DELIVER_SM_RESP: DeliverSmResp,
    SmppCommand.BIND_TRANSCEIVER: BindTransceiver,
    SmppCommand.BIND_TRANSCEIVER_RESP: BindTransceiverResp,
    SmppCommand.BIND_TRANSMITTER: BindTransmitter,
    SmppCommand.BIND_TRANSMITTER_RESP: BindTransmitterResp,
    SmppCommand.BIND_RECEIVER: BindReceiver,
    SmppCommand.BIND_RECEIVER_RESP: BindReceiverResp,
    SmppCommand.ENQUIRE_LINK: EnquireLink,
    SmppCommand.ENQUIRE_LINK_RESP: EnquireLinkResp,
    SmppCommand.UNBIND: Unbind,
    SmppCommand.UNBIND_RESP: UnbindResp,
}
