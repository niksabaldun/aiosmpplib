import dataclasses
from datetime import datetime, timedelta

from .protocol import MESSAGE_TYPE_MAP, SmppMessage
from .state import SmppCommand
from .utils import AnyDict

try:
    import orjson
    from orjson import loads as json_loads
    def json_encode(obj: object) -> str:
        return orjson.dumps(obj, default=_json_default,
                            option=orjson.OPT_PASSTHROUGH_DATACLASS).decode('utf-8')
except ImportError:
    import json
    from json import loads as json_loads
    def json_encode(obj: object) -> str:
        return json.dumps(obj, default=_json_default)


def _json_default(o: object) -> object:
    if isinstance(o, timedelta):
        return o.total_seconds()
    if isinstance(o, datetime):
        return o.isoformat()
    if isinstance(o, SmppMessage):
        result: AnyDict = {'__smpp_command__': o.smpp_command.name}
        result.update({key: value for key, value in o.__dict__.items() if not key.startswith('_')})
        return result
    if dataclasses.is_dataclass(o):
        return o.__dict__
    raise TypeError(f'Object of type {o.__class__.__name__} '
                    f'is not JSON serializable')


def dict_to_smpp_message(obj: AnyDict) -> SmppMessage:
    smpp_command_str: object = obj.get('__smpp_command__')
    if not smpp_command_str or not isinstance(smpp_command_str, str):
        raise ValueError('Invalid JSON object: not a SMPP message')
    smpp_command: SmppCommand = SmppCommand[smpp_command_str]
    message_class: type[SmppMessage]= MESSAGE_TYPE_MAP[smpp_command]
    return message_class.from_json(obj)


def json_decode(json_data: str | bytes) -> SmppMessage:
    json_object: AnyDict = json_loads(json_data)
    if not isinstance(json_object, dict):
        raise ValueError('Invalid JSON string')
    return dict_to_smpp_message(json_object)
