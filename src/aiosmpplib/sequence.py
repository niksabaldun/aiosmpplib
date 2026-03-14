from abc import ABC, abstractmethod

MIN_SEQUENCE_NUMBER: int = 0x00000001
MAX_SEQUENCE_NUMBER: int = 0x7FFFFFFF


def assert_valid_sequence(sequence_num: int) -> None:
    if not MIN_SEQUENCE_NUMBER <= sequence_num <= MAX_SEQUENCE_NUMBER:
        raise ValueError(f'The sequence_num: {sequence_num} is outside of limits '
                         f'{MIN_SEQUENCE_NUMBER}-{MAX_SEQUENCE_NUMBER} allowed by SMPP spec.')


class AbstractSequenceGenerator(ABC):
    '''
    Interface that must be implemented to satisfy aiosmpplib sequence generator.
    User implementations should inherit this class and
    implement the :func:`next_sequence <AbstractSequenceGenerator.next_sequence>` methods.

    In SMPP, sequence_num is an Integer which allows requests and responses to be correlated.
    The sequence_num should increase monotonically and be in the range `1` to `2,147,483,647`

    The sequence_num should wrap around when it reaches the maximum allowed by specification.
    '''

    @abstractmethod
    def next_sequence(self) -> int:
        '''
        Returns a monotonically increasing integer in the range `1` to `2,147,483,647`
        '''
        raise NotImplementedError()


class SimpleSequenceGenerator(AbstractSequenceGenerator):
    '''
    This is an implementation of AbstractSequenceGenerator.
    '''

    def __init__(self, min_num: int=MIN_SEQUENCE_NUMBER, max_num=MAX_SEQUENCE_NUMBER) -> None:
        self.min_num: int = min_num
        self.max_num: int = max_num
        self.sequence_num: int = min_num - 1

    def next_sequence(self) -> int:
        if self.sequence_num == self.max_num:
            # Wrap around
            self.sequence_num = self.min_num
        else:
            self.sequence_num += 1
        return self.sequence_num
