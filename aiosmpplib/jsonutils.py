import dataclasses
from datetime import datetime, timedelta
from typing import Any, Dict, Type, Union
from .protocol import SmppMessage, MESSAGE_TYPE_MAP
from .state import SmppCommand
try:
    import orjson
    from orjson import loads as json_loads

    def json_encode(obj: Any) -> str:
        return orjson.dumps(obj, default=_json_default, option=orjson.OPT_PASSTHROUGH_DATACLASS).decode('utf-8')
except ImportError:
    import json
    from json import loads as json_loads

    def json_encode(obj: Any) -> str:
        return json.dumps(obj, default=_json_default)


def _json_default(o: Any) -> Any:
    if isinstance(o, timedelta):
        return o.total_seconds()
    if isinstance(o, datetime):
        return o.isoformat()
    if isinstance(o, SmppMessage):
        result: Dict[str, Any] = {'__smpp_command__': o.smpp_command.name}
        result.update(o.__dict__)
        return result
    if dataclasses.is_dataclass(o):
        return o.__dict__
    raise TypeError(f'Object of type {o.__class__.__name__} '
                    f'is not JSON serializable')


def json_decode(json_data: Union[str, bytes]) -> SmppMessage:
    json_object: Dict[str, Any] = json_loads(json_data)
    if not isinstance(json_object, dict):
        raise ValueError('Invalid JSON string')
    smpp_command_str = json_object.get('__smpp_command__', '')
    if not smpp_command_str:
        raise ValueError('Invalid JSON object: not a SMPP message')
    smpp_command: SmppCommand = SmppCommand[smpp_command_str]
    message_class: Type[SmppMessage] = MESSAGE_TYPE_MAP[smpp_command]
    return message_class.from_json(json_object)
