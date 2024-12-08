from datetime import datetime, timedelta, tzinfo
from random import randint
from struct import pack
from typing import Any, List, Optional, Tuple, Type, Union
from .codec import ESCAPE, GSM7BitCodec, UCS2Codec


# Max single SMS sizes
MAX_OCTET_SIZE: int = 140
MAX_SEPTET_SIZE: int = 160
MAX_SM_SIZE: int = 254

# Concatenated message reference types
IE_ID_8BIT: int = 0x00
IE_ID_16BIT: int = 0x08


def check_param(param: Any, param_name: str, param_type: Union[Type, Tuple[Type, ...]],
                optional: bool=False, maxlen: int = 0) -> None:
    if param is None:
        if not optional:
            raise ValueError(f'Non-optional parameter `{param_name}` was set to None.')
        return
    if not isinstance(param, param_type):
        if isinstance(param_type, Type):
            type_names: str = f'`{param_type.__name__}`'
        else:
            type_names: str = ' or '.join(f'`{typ.__name__}`' for typ in param_type)
        raise ValueError(f'Parameter `{param_name}` must be of type {type_names} '
                         f'and `{type(param).__name__}` type was provided.')
    if maxlen > 0:
        if isinstance(param, str) and len(param) > maxlen:
            raise ValueError(f'Parameter `{param_name}` maximum length  is {maxlen} '
                             f'and the length of provided value is `{len(param)}`.')
        if isinstance(param, int) and (param.bit_length() + 7) // 8 > maxlen:
            raise ValueError(f'Parameter `{param_name}` maximum byte length  is {maxlen} and the '
                             f'length of provided value is `{(param.bit_length() + 7) // 8}`.')


class FixedOffset(tzinfo):
    """Fixed offset from UTC."""

    def __init__(self, offset: Union[timedelta, int], name: str) -> None:
        if isinstance(offset, timedelta):
            self.offset: timedelta = offset
        else:
            self.offset: timedelta = timedelta(minutes=offset)
        self._name = name

    def tzname(self, dt: Optional[datetime]) -> str:
        # pylint: disable=unused-argument
        return self._name

    def utcoffset(self, dt: Optional[datetime]) -> timedelta:
        # pylint: disable=unused-argument
        return self.offset

    def dst(self, dt: Optional[datetime]) -> timedelta:
        # pylint: disable=unused-argument
        return timedelta(0)

    @classmethod
    def from_timezone(cls, offset_str: str, name: str='') -> 'FixedOffset':
        '''
        Parameters:
            offset_str: Timezone part of datetime in ISO8601 format, e.g. '+0100' or '-0300'
            name: Timezone name
        '''
        if not offset_str:
            return cls(timedelta(0), name)
        if not name:
            name = 'UTC' + offset_str

        sign: int = 1 if '+' in offset_str else -1
        hours: int = int(offset_str[1:3])
        minutes: int = int(offset_str[3:])
        minutes += hours * 60

        if sign == 1:
            time_delta: timedelta = timedelta(minutes=minutes)
        else:
            time_delta: timedelta = timedelta(days=-1, minutes=minutes)

        return cls(time_delta, name)


def detect_format(text: str) -> str:
    if GSM7BitCodec.is_gsm_text(text):
        return 'gsm0338'
    else:
        return 'ucs2'


def encode_user_data(user_data: bytes, data_len: int) -> bytes:
    return pack('!B', data_len) + user_data


def split_sms(text: str, encoding: str = '') -> List[bytes]:
    if not encoding:
        encoding = detect_format(text)

    total_len: int
    text_bytes: bytes
    if encoding == 'gsm0338':
        total_len = len(text)
        if total_len <= MAX_SM_SIZE:
            # Fits in one SMS
            text_bytes, total_len = GSM7BitCodec.get_codec_info().encode(text)
            return [encode_user_data(text_bytes, total_len)]
    else:
        text_bytes, total_len = UCS2Codec.get_codec_info().encode(text)
        total_len = len(text_bytes)
        if total_len <= MAX_SM_SIZE:
            # Fits in one SMS
            return [encode_user_data(text_bytes, total_len)]

    pdu_msgs: List[bytes]
    if encoding == 'gsm0338':
        text_msgs: List[str] = []
        start: int = 0
        end: int = MAX_SM_SIZE
        while start < total_len:
            if end - start == MAX_SM_SIZE:
                end_char: str = text[end - 1]
                if end_char == chr(ESCAPE):
                    # GSM 03.38 escape code, must not unpair it from extended char
                    end -= 1
            text_msgs.append(text[start:end])
            start = end
            end += MAX_SM_SIZE
            if end > total_len:
                end = total_len
        pdu_msgs = [GSM7BitCodec.get_codec_info().encode(msg)[0] for msg in text_msgs]
    else:
        pdu_msgs = []
        start: int = 0
        end: int = MAX_SM_SIZE
        while start < total_len:
            if end - start == MAX_SM_SIZE:
                end_byte: int = text_bytes[end - 2]  # type: ignore ; must be bound
                if 0xD8 <= end_byte <= 0xDB:
                    # UTF-16 high surrogate, must not unpair it from low surrogate
                    end -= 2
            pdu_msgs.append(text_bytes[start:end])  # type: ignore ; must be bound
            start = end
            end += MAX_SM_SIZE
            if end > total_len:
                end = total_len

    return pdu_msgs


def split_sms_udh(text: str, encoding: str = '', csms_ref: Optional[int] = None) -> List[bytes]:
    # If CSMS reference number is larger than 255, it will take two bytes
    if csms_ref is None:
        csms_ref = randint(0x00, 0xFF)
    if csms_ref > 0xFF:
        udh_len: int = 0x06
        udh_data_len: int = 0x04
        ie_id: int = IE_ID_16BIT
    else:
        udh_len: int = 0x05
        udh_data_len: int = 0x03
        ie_id: int = IE_ID_8BIT

    if not encoding:
        encoding = detect_format(text)

    total_len: int
    text_bytes: bytes
    if encoding == 'gsm0338':
        total_len = len(text)
        if total_len <= MAX_SEPTET_SIZE:
            # Fits in one SMS
            text_bytes, total_len = GSM7BitCodec.get_codec_info().encode(text)
            return [encode_user_data(text_bytes, total_len)]
        len_without_udh: int = MAX_SEPTET_SIZE - udh_len - 2
    else:
        text_bytes, total_len = UCS2Codec.get_codec_info().encode(text)
        total_len = len(text_bytes)
        if total_len <= MAX_OCTET_SIZE:
            # Fits in one SMS
            return [encode_user_data(text_bytes, total_len)]
        # UDH takes a total of 6 or 7 bytes. If 7, we must subtract additional byte
        # as each char in UCS2 takes two bytes, so total number of bytes must be even
        len_without_udh: int = MAX_OCTET_SIZE - udh_len - 1 - ((udh_len + 1) % 2)

    pdu_msgs: List[bytes] = []
    udh: bytearray = bytearray()
    udh.append(udh_len)
    udh.append(ie_id)
    udh.append(udh_data_len)
    if csms_ref > 255:
        udh.append(csms_ref >> 8)
        udh.append(csms_ref & 0xFF)
    else:
        udh.append(csms_ref)

    if encoding == 'gsm0338':
        text_msgs: List[str] = []
        start: int = 0
        end: int = len_without_udh
        while start < total_len:
            if end - start == len_without_udh:
                end_char: str = text[end - 1]
                if end_char == chr(ESCAPE):
                    # GSM 03.38 escape code, must not unpair it from extended char
                    end -= 1
            text_msgs.append(text[start:end])
            start = end
            end += len_without_udh
            if end > total_len:
                end = total_len
        udh.append(len(text_msgs))
        udh.append(0)
        for index, msg in enumerate(text_msgs):
            msg_bytes: bytes
            msg_bytes, _msg_len = GSM7BitCodec.get_codec_info().encode(msg)
            udh[udh_len] = index + 1
            pdu_msgs.append(bytes(udh) + msg_bytes)
    else:
        byte_msgs: List[bytes] = []
        start: int = 0
        end: int = len_without_udh
        while start < total_len:
            if end - start == len_without_udh:
                end_byte: int = text_bytes[end - 2]  # type: ignore ; must be bound
                if 0xD8 <= end_byte <= 0xDB:
                    # UTF-16 high surrogate, must not unpair it from low surrogate
                    end -= 2
            byte_msgs.append(text_bytes[start:end])  # type: ignore ; must be bound
            start = end
            end += len_without_udh
            if end > total_len:
                end = total_len
        udh.append(len(byte_msgs))
        udh.append(0)
        for index, msg_bytes in enumerate(byte_msgs):
            udh[udh_len] = index + 1
            pdu_msgs.append(bytes(udh) + msg_bytes)

    return pdu_msgs
