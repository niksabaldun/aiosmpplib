import json
from datetime import datetime, timedelta
from enum import IntEnum
from typing import Any, Dict, Optional, Type
from .protocol import SmppMessage, MESSAGE_TYPE_MAP
from .state import (NPI, TON, OptionalParam, OptionalTag, PhoneNumber, SmppCommand,
                    SmppCommandStatus, PduHeader)


_INT_ENUM_PARAMS: Dict[str, Type[IntEnum]] = {
    'command_status': SmppCommandStatus,
    'tag': OptionalTag,
}


class SmppJsonEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any: # pylint: disable=method-hidden; problem is in base module
        if isinstance(o, datetime):
            return {
                '__type__': type(o).__name__,
                'year': o.year,
                'month': o.month,
                'day': o.day,
                'hour': o.hour,
                'minute': o.minute,
                'second': o.second,
                'microsecond': o.microsecond,
            }
        if isinstance(o, timedelta):
            return {
                '__type__': type(o).__name__,
                'days': o.days,
                'seconds': o.seconds,
                'microseconds': o.microseconds,
            }
        if isinstance(o, OptionalParam):
            return {
                '__type__': type(o).__name__,
                'tag': o.tag.name,
                'value': o.value,
            }
        if isinstance(o, PhoneNumber):
            return {
                '__type__': type(o).__name__,
                'number': o.number,
                'ton': o.ton.name,
                'npi': o.npi.name,
            }
        if isinstance(o, PduHeader):
            # Just for logging, no deserialization
            return (f'PduHeader(pdu_length={o.pdu_length}, smpp_command={o.smpp_command.name}, '
                    f'command_status={o.command_status.name}, sequence_num={o.sequence_num})')
        if isinstance(o, SmppMessage):
            return {
                '__smpp_command__': o.smpp_command.name,
                **o.as_dict()
            }
        return json.JSONEncoder.default(self, o)


class SmppJsonDecoder(json.JSONDecoder):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, object_hook=self.convert_object, **kwargs)

    def convert_message_param(self, param: str, value: Any) -> Any:
        if isinstance(value, dict):
            return self.convert_object(value)
        if param in _INT_ENUM_PARAMS:
            return _INT_ENUM_PARAMS[param](value)
        return value

    def convert_object(self, o: dict) -> Any:
        smpp_command_str: Optional[str] = o.pop('__smpp_command__', None)
        if smpp_command_str:
            try:
                smpp_command: SmppCommand = SmppCommand[smpp_command_str]
                message_class: Type[SmppMessage]= MESSAGE_TYPE_MAP[smpp_command]
                message_dict: dict = {param: self.convert_message_param(param, value)
                                      for param, value in o.items()}
                return message_class(**message_dict)
            except: # pylint: disable=bare-except
                pass
            o['__smpp_command__'] = smpp_command_str
        obj_type: Optional[str] = o.pop('__type__', None)
        if obj_type:
            try:
                if obj_type == 'datetime':
                    return datetime(**o)
                if obj_type == 'timedelta':
                    return timedelta(**o)
                if obj_type == 'OptionalParam':
                    return OptionalParam(tag=OptionalTag[o['tag']], value=o['value'])
                if obj_type == 'PhoneNumber':
                    return PhoneNumber(number=o['number'], ton=TON[o['ton']], npi=NPI[o['npi']])
            except: # pylint: disable=bare-except
                pass
            o['__type__'] = obj_type
        return o


def json_encode(obj: Any):
    return json.dumps(obj, cls=SmppJsonEncoder)


def json_decode(json_data: str):
    return json.loads(json_data, cls=SmppJsonDecoder)
