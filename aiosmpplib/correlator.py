import os
import time
from collections.abc import Mapping
from dataclasses import dataclass
from abc import ABC, abstractmethod
from types import EllipsisType
from typing import Any, Dict, Iterator, MutableMapping, Optional, Tuple, TypeVar, Union
from .hook import AbstractHook
from .jsonutils import dict_to_smpp_message, json_encode, json_loads
from .protocol import DeliverSm, SmppMessage, SubmitSm
from .state import DLR_ERROR_OTHER_ERROR, SmppCommand, SmppCommandStatus
from .utils import check_param


STATUS_SENDING = 65535
STATUS_FAILED = 65534
STATUS_EXPIRED = 65533
STATUS_SENT = 65532

_EXPIRED_ERROR: TimeoutError = TimeoutError('No response to command received within timeout')

VT = TypeVar('VT')


@dataclass
class SegmentStatus:
    status: Dict[str, int]  # Status of individual segments (seq_num: status_code)
    orig_submit_sm: SubmitSm  # Original SubmitSm that is being segmented
    last_response: Optional[SmppMessage] = (
        None  # Last response, or last failed response if there was a failure
    )
    last_receipt: Optional[DeliverSm] = (
        None  # Last delivery receipt, or last failed receipt if there was a failure
    )


class PersistingDict(MutableMapping[str, VT]):
    def __init__(self, directory: str, file_name: str, /, **kwargs: Any) -> None:
        self._data: Dict[str, VT] = {}
        self._file_name: str = os.path.join(directory, file_name) if directory else ''
        if self._file_name:
            try:
                with open(self._file_name, 'rb') as json_file:
                    data: Union[Any, Dict[str, Any]] = json_loads(json_file.read())
                    if isinstance(data, dict):
                        for key, value in data.items():
                            if isinstance(value, dict):
                                data[key] = self._process_object(value)
                            elif isinstance(value, list):
                                for ind, member in enumerate(value):
                                    if isinstance(member, dict):
                                        value[ind] = self._process_object(member)
                    self._data = data
            except Exception:
                pass

    @staticmethod
    def _process_object(obj: Dict[str, Any]) -> Any:
        if '__smpp_command__' in obj:
            return dict_to_smpp_message(obj)
        if 'orig_submit_sm' in obj:
            return SegmentStatus(**obj)
        return obj

    def _save(self):
        if self._file_name:
            with open(self._file_name, 'w') as json_file:
                json_file.write(json_encode(self._data))

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def __delitem__(self, key: str) -> None:
        del self._data[key]
        self._save()

    def __getitem__(self, key: str) -> VT:
        if key in self._data:
            return self._data[key]
        raise KeyError(key)

    def __len__(self) -> int:
        return len(self._data)

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __setitem__(self, key: str, value: VT) -> None:
        self._data[key] = value
        self._save()

    def pop(self, key: str, default: Optional[Union[VT, EllipsisType]] = ...) -> Optional[VT]:
        if key in self._data:
            item: VT = self._data.pop(key)
            self._save()
            return item
        if default is ...:
            raise KeyError(key)
        return default

    def update(self, other=(), /, **kwds) -> None:
        if isinstance(other, Mapping):
            for key in other:
                self._data[key] = other[key]
        elif hasattr(other, 'keys'):
            for key in other.keys():
                self._data[key] = other[key]
        else:
            for key, value in other:
                self._data[key] = value
        for key, value in kwds.items():
            self._data[key] = value


class AbstractCorrelator(ABC):
    '''
    Interface that must be implemented to satisfy aiosmpplib Correlator.
    User implementations should inherit this class and
    implement the :func:`get <AbstractCorrelator.get>`, :func:`put <AbstractCorrelator.put>`,
    :func:`get <AbstractCorrelator.get_segmented>`,
    :func:`get <AbstractCorrelator.get_delivery>`,
    :func:`put <AbstractCorrelator.put_delivery>` and
    :func:`put <AbstractCorrelator.put_delivery_segmented>` methods.

    A Correlator is class that is used to store relations between SMPP requests and replies.
    Correlation is based on sequence number, and optionally message type,
    though running out of sequence numbers is normally not a concern.

    If the SubmitSm needs to be segmented, segments are correlated with the original message.
    This correlation is based on segmentation reference number and sequence number of
    individual segments.

    Segmented DeliverSm messages are correlated based on segmentation reference number.

    SubmitSm requests are also correlated with DeliverSm delivery receipts.
    This correlation is based on message_id provided by SMSC.
    Delivery receipt may arrive days after sending, so this correlation should be persisted.
    Consequently, correlation of segmented message should be persisted as well.

    User application provides log_id and optionally extra_data,
    which it can use for its own correlation.

    SubmitSm Correlation is based on message ID received in delivery report, which can
    either be in receipted_message_id optional parameter or in message text.
    '''

    # Parent MUST set these properties before use
    hook: AbstractHook = None  # type: ignore
    client_id: str = None  # type: ignore

    @abstractmethod
    def get_cumulated_status(self, ref_num: int) -> int:
        '''
        Get cumulated status of a segmented message by reference number

        Parameters:
            smpp_message: Protocol message whose correlation data has expired.
        '''
        raise NotImplementedError()

    @abstractmethod
    async def expired(self, smpp_message: SmppMessage) -> None:
        '''
        Correlator implementation MUST call this method whenever correlation data expires
        before receiving a response from SMPP peer.

        Parameters:
            smpp_message: Protocol message whose correlation data has expired.
        '''
        raise NotImplementedError()

    @abstractmethod
    async def put(self, smpp_message: SmppMessage) -> None:
        '''
        Called to store the correlation between a SMPP sequence number and sent message,
        and also between a segmented SubmitSm and segmentation reference number.

        Parameters:
            smpp_message: Protocol message that should be correlated.
        '''
        raise NotImplementedError()

    @abstractmethod
    async def put_delivery(self, smsc_message_id: str, submit_sm: SubmitSm) -> None:
        '''
        Called to store the correlation between a SubmitSm and a DeliverSm receipt.

        Parameters:
            smsc_message_id: Unique identifier of a message on the SMSC. It comes from SMSC.
            submit_sm: SubmitSm that should be correlated
        '''
        raise NotImplementedError()

    @abstractmethod
    async def put_delivery_segmented(self, deliver_sm: DeliverSm) -> Optional[DeliverSm]:
        '''
        Called to store the segmented DeliverSm and optionally return
        full DeliverSm once all segments are received.

        Parameters:
            deliver_sm: DeliverSm segment

        Returns:
            Full DeliverSm, if all segments are received
        '''
        raise NotImplementedError()

    @abstractmethod
    async def get(self, smpp_command: SmppCommand, response: SmppMessage) -> Optional[SmppMessage]:
        '''
        Called to get the correlation between a SMPP sequence number and sent message.

        Parameters:
            smpp_command: Any one of the SMSC commands eg submit_sm
            response: SMPP response containing SMPP sequence_num

        Returns:
            Correlated Message object, if any
        '''
        raise NotImplementedError()

    @abstractmethod
    async def get_segmented(
        self, smpp_seq_num: int, remove: bool = False
    ) -> Tuple[Optional[SegmentStatus], int]:
        '''
        Called to get the correlation between a segmented SubmitSm
        and its specific segment.

        Parameters:
            smpp_seq_num: SMPP sequence number of SubmitSm segment
            remove: Whether to remove the correlation

        Returns:
            SegmentStatus object and cumulated status, if any
        '''
        raise NotImplementedError()

    @abstractmethod
    async def get_delivery(self, receipt: DeliverSm) -> Optional[SubmitSm]:
        '''
        Called to get the correlation between a SubmitSm and a DeliverSm receipt.

        Parameters:
            receipt: DeliverSm containing delivery receipt. Its 'id' member must contain the unique
                     identifier of the original message, which comes from SMSC. The 'err' member
                     should contain the error code (0 if there is no error).

        Returns:
            A correlated SubmitSm message or None if not found
        '''
        raise NotImplementedError()


class SimpleCorrelator(AbstractCorrelator):
    '''
    A simple implementation of AbstractCorrelator.
    It manages the correlation between SMPP requests and responses,
    between segmented message and its parts
    and between SubmitSM requests and DeliverSm receipts.
    WARNING: Not suitable for production!
             Correlation between SubmitSm and DeliverSM should be persisted.

    SimpleCorrelator also features an auto-expiration of dictionary items based on time.

    The storage is done in memory using a python dictionary. The storage looks like:

    .. highlight:: python
    .. code-block:: python

       {
            'sequence_num1': (681.109023565, EnquireLink()),
            'sequence_num1': (681.209023888, SubmitSm()),
            ...
       }
       {
            'smsc_message_id1': (681.109023565, 'log_id1', 'hook_metadata1'),
            'smsc_message_id2': (682.109023565, 'log_id2', 'hook_metadata2'),
            ...
       }
    '''

    def __init__(
        self,
        name: str,
        directory: str = '',
        max_ttl_response: float = 15.00,
        max_ttl_delivery: float = 259200.00,
    ) -> None:
        '''
        Parameters:
            name: Correlator name
            directory: Filesystem directory in which to persist the correlation data
            max_ttl_response: The time in seconds that a request/response correlation will be stored
            max_ttl_delivery: The time in seconds that a submit/delivery correlation will be stored
        '''
        check_param(max_ttl_response, 'max_ttl_response', float)
        if max_ttl_response < 1.00:
            raise ValueError(
                f'Parameter max_ttl_response ({max_ttl_response}) must not be less than 1 second.'
            )
        check_param(max_ttl_delivery, 'max_ttl_delivery', float)
        if max_ttl_delivery < 1.00:
            raise ValueError(
                f'Parameter max_ttl_delivery ({max_ttl_delivery}) must not be less than 1 second.'
            )
        self.max_ttl_response: float = max_ttl_response
        self.max_ttl_delivery: float = max_ttl_delivery
        # Dict keys are string for easier serialization
        self._store: PersistingDict[Tuple[float, SmppMessage]] = PersistingDict(
            directory, name + '_store.json'
        )  # seq_num: (stored_at, message)
        self._segment_store: PersistingDict[Tuple[int, int]] = PersistingDict(
            directory, name + '_segment_store.json'
        )  # seq_num: (ref_num, segment_seq_num)
        self._segment_status_store: PersistingDict[SegmentStatus] = PersistingDict(
            directory, name + '_segment_status_store.json'
        )  # ref_num: segment_status
        self._delivery_store: PersistingDict[Tuple[float, SubmitSm]] = PersistingDict(
            directory, name + '_delivery_store.json'
        )  # msg_id: (stored_at, submit_sm)
        self._delivery_segment_store: PersistingDict[Tuple[float, Dict[str, str]]] = PersistingDict(
            directory, name + '_delivery_segment_store.json'
        )  # ref_num: (stored_at, {seq_num: segment_text})

    def get_cumulated_status(self, ref_num: int) -> int:
        ref_key: str = str(ref_num)
        segment_status: SegmentStatus = self._segment_status_store[ref_key]
        if not segment_status.status:
            return STATUS_SENDING
        status_code: int = max(segment_status.status.values())
        if status_code not in (STATUS_SENDING, STATUS_SENT):
            # All segments either failed, expired or got a status report
            del self._segment_status_store[ref_key]
        return status_code

    async def expired(self, smpp_message: SmppMessage) -> None:
        if isinstance(smpp_message, SubmitSm):
            sequence_key: str = str(smpp_message.sequence_num)
            if sequence_key in self._segment_store.keys():
                ref_num, seq_num = self._segment_store.pop(sequence_key)  # type: ignore ; we check for key existence
                segment_status: Optional[SegmentStatus] = self._segment_status_store.get(
                    str(ref_num)
                )
                if segment_status:
                    segment_status.status[str(seq_num)] = STATUS_EXPIRED
                    if self.get_cumulated_status(ref_num) == STATUS_EXPIRED:
                        await self.hook.send_error(
                            segment_status.orig_submit_sm, _EXPIRED_ERROR, self.client_id
                        )
            else:
                await self.hook.send_error(smpp_message, _EXPIRED_ERROR, self.client_id)

    async def put(self, smpp_message: SmppMessage) -> None:
        await self._remove_expired()
        stored_at: float = time.monotonic()
        seq_key: str = str(smpp_message.sequence_num)
        self._store[seq_key] = (stored_at, smpp_message)
        if isinstance(smpp_message, SubmitSm):
            ref_num, seq_num, total_segments = smpp_message.get_segmentation_data()
            if total_segments > 0:
                # This is a part of a segmented message
                self._segment_store[seq_key] = (ref_num, seq_num)
                key: str = str(ref_num)
                segment_status: SegmentStatus
                if key in self._segment_status_store:
                    segment_status = self._segment_status_store[str(ref_num)]
                else:
                    segment_status = SegmentStatus({}, smpp_message)
                    self._segment_status_store[key] = segment_status
                segment_status.status[str(seq_num)] = STATUS_SENDING

    async def put_delivery(self, smsc_message_id: str, submit_sm: SubmitSm) -> None:
        await self._remove_expired()
        stored_at: float = time.monotonic()
        self._delivery_store[smsc_message_id] = (stored_at, submit_sm)

    async def put_delivery_segmented(self, deliver_sm: DeliverSm) -> Optional[DeliverSm]:
        stored_at: float = time.monotonic()
        text = deliver_sm.short_message or deliver_sm.message_payload
        ref_num, seq_num, total_segments = deliver_sm.get_segmentation_data()
        segment_data: Optional[Tuple[float, Dict[str, str]]] = self._delivery_segment_store.get(
            str(ref_num)
        )
        segments: Dict[str, str]
        if not segment_data:
            segments = {str(seq_num): text}
            segment_data = (stored_at, segments)
        else:
            segments = segment_data[1]
            segments[str(seq_num)] = text
            segment_data = (stored_at, segments)
        if len(segments) == total_segments:
            text = ''.join(v for k, v in sorted(segments.items()))
            if deliver_sm.short_message:
                deliver_sm.short_message = text
            else:
                deliver_sm.message_payload = text
            del self._delivery_segment_store[str(ref_num)]
            await self._remove_expired()
            return deliver_sm
        self._delivery_segment_store[str(ref_num)] = segment_data
        await self._remove_expired()
        return None

    async def get(self, smpp_command: SmppCommand, response: SmppMessage) -> Optional[SmppMessage]:
        sequence_key: str = str(response.sequence_num)
        item: Optional[Tuple[float, SmppMessage]] = self._store.pop(sequence_key, None)
        smpp_message: Optional[SmppMessage] = None
        if item:
            smpp_message = item[1]
            if isinstance(smpp_message, SubmitSm):
                if sequence_key in self._segment_store:
                    ref_num, seq_num = self._segment_store[sequence_key]
                    segment_status: Optional[SegmentStatus] = self._segment_status_store.get(
                        str(ref_num)
                    )
                    if segment_status:
                        if response.smpp_command == SmppCommand.GENERIC_NACK:
                            segment_status.status[str(seq_num)] = STATUS_FAILED
                            segment_status.last_response = response
                        else:
                            if response.command_status == SmppCommandStatus.ESME_ROK:
                                segment_status.status[str(seq_num)] = STATUS_SENT
                                if not segment_status.last_response:
                                    segment_status.last_response = response
                            else:
                                segment_status.status[str(seq_num)] = STATUS_FAILED
                                segment_status.last_response = response
        await self._remove_expired()
        return smpp_message

    async def get_segmented(
        self, smpp_seq_num: int, remove: bool = False
    ) -> Tuple[Optional[SegmentStatus], int]:
        item: Optional[Tuple[int, int]] = self._segment_store.get(str(smpp_seq_num))
        if not item:
            return None, 0
        if remove:
            del self._segment_store[str(smpp_seq_num)]
        ref_num: int = item[0]
        segment_status: Optional[SegmentStatus] = self._segment_status_store.get(str(ref_num))
        if not segment_status:
            # This should not happen
            return None, 0
        status_code: int = self.get_cumulated_status(ref_num)
        return segment_status, status_code

    async def get_delivery(self, receipt: DeliverSm) -> Optional[SubmitSm]:
        receipt_dict: Dict[str, Any] = receipt.parse_receipt()
        smsc_message_id: str = receipt_dict.get('id', '')
        item: Optional[Tuple[float, SubmitSm]] = self._delivery_store.pop(smsc_message_id, None)
        submit_sm: Optional[SubmitSm] = item[1] if item else None
        if submit_sm and str(submit_sm.sequence_num) in self._segment_store.keys():
            error_code: int = receipt_dict.get('err', DLR_ERROR_OTHER_ERROR)
            ref_num, seq_num = self._segment_store[str(submit_sm.sequence_num)]
            segment_status: Optional[SegmentStatus] = self._segment_status_store.get(str(ref_num))
            if segment_status:
                segment_status.status[str(seq_num)] = error_code
                if error_code > 0 or not segment_status.last_receipt:
                    segment_status.last_receipt = receipt
        await self._remove_expired()
        return submit_sm

    async def _remove_expired(self) -> None:
        now: float = time.monotonic()
        sequence_key: str
        for sequence_key in tuple(self._store.keys()):
            stored_at: float
            message: SmppMessage
            stored_at, message = self._store[sequence_key]
            if now - stored_at > self.max_ttl_response:
                del self._store[sequence_key]
                await self.expired(message)

        for key, value in list(self._delivery_store.items()):
            if now - value[0] > self.max_ttl_delivery:
                del self._delivery_store[key]

        for key, value in list(self._delivery_segment_store.items()):
            if now - value[0] > self.max_ttl_delivery:
                del self._delivery_segment_store[key]
