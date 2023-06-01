from datetime import datetime, timedelta, tzinfo
from typing import Any, Optional, Tuple, Type, Union


def check_param(param: Any,
                param_name: str,
                param_type: Union[Type, Tuple[Type]],
                optional: bool = False,
                maxlen: int = 0) -> None:
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
    if maxlen > 0 and isinstance(param, str) and len(param) > maxlen:
        raise ValueError(f'Parameter `{param_name}` maximum length  is {maxlen} '
                         f'and the length of provided value is `{len(param)}`.')


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
    def from_timezone(cls, offset_str: str, name: str = '') -> 'FixedOffset':
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
