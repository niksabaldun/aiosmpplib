from datetime import datetime
from typing import Any, Dict, List, Tuple
import pytest
from aiosmpplib.protocol import DEFAULT_ENCODING, SMPP_VERSION_3_4
from aiosmpplib import json_decode, json_encode
from aiosmpplib import PhoneNumber, TON, NPI, OptionalParam, OptionalTag
from aiosmpplib import (SubmitSm, SubmitSmResp, DeliverSm, DeliverSmResp, Unbind, UnbindResp,
                        BindTransceiver, BindTransceiverResp, BindReceiver, BindReceiverResp,
                        BindTransmitter, BindTransmitterResp, EnquireLink, EnquireLinkResp,
                        SmppMessage, PduHeader, GenericNack)


BIND_TRANSCEIVER = BindTransceiver(
    system_id='testuser',
    password='password',
    system_type='',
    interface_version=SMPP_VERSION_3_4,
    addr_ton=TON.ALPHANUMERIC,
    addr_npi=NPI.UNKNOWN,
    address_range='',
    sequence_num=1,
)
BIND_TRANSCEIVER_RESP = BindTransceiverResp(
    system_id='testuser',
    sc_interface_version=SMPP_VERSION_3_4,
    sequence_num=1,
)
BIND_TRANSMITTER = BindTransmitter(**BIND_TRANSCEIVER.__dict__)
BIND_TRANSMITTER_RESP = BindTransmitterResp(**BIND_TRANSCEIVER_RESP.__dict__)
BIND_RECEIVER = BindReceiver(**BIND_TRANSCEIVER.__dict__)
BIND_RECEIVER_RESP = BindReceiverResp(**BIND_TRANSCEIVER_RESP.__dict__)
SUBMIT_SM: SubmitSm = SubmitSm(
    short_message='Test message',
    source=PhoneNumber('INFO', TON.ALPHANUMERIC),
    destination=PhoneNumber('+123135654618'),
    sequence_num=1,
)
SUBMIT_SM_WITH_PAYLOAD: SubmitSm = SubmitSm(
    short_message='',
    message_payload='😇😇😇😇😇😇😇😇😇😇😇😇😇😇😇😇😇😇😇😇😇😇😇😇😇😇😇😇😇😇😇😇😇',
    source=PhoneNumber('INFO', TON.ALPHANUMERIC),
    destination=PhoneNumber('+123135654618'),
    sequence_num=1,
)
SUBMIT_SM_WITH_OPT_PARAMS: SubmitSm = SubmitSm(
    short_message='Test message',
    source=PhoneNumber('INFO', TON.ALPHANUMERIC),
    destination=PhoneNumber('+123135654618'),
    optional_params=[
        OptionalParam(OptionalTag.ALERT_ON_MESSAGE_DELIVERY, True),
        OptionalParam(OptionalTag.DEST_SUBADDRESS, '555'),
        OptionalParam(OptionalTag.DEST_NETWORK_TYPE, 1),
    ],
    sequence_num=1,
)
DELIVER_SM: DeliverSm = DeliverSm(
    short_message='Test message',
    source=PhoneNumber('INFO', TON.ALPHANUMERIC),
    destination=PhoneNumber('+123135654618'),
    sequence_num=1,
)
TEST_MESSAGES: List[Tuple[str, SmppMessage]] = [
    ('BindTransceiver', BIND_TRANSCEIVER),
    ('BindTransceiverResp', BIND_TRANSCEIVER_RESP),
    ('BindTransmitter', BIND_TRANSMITTER),
    ('BindTransmitterResp', BIND_TRANSMITTER_RESP),
    ('BindReceiver', BIND_RECEIVER),
    ('BindReceiverResp', BIND_RECEIVER_RESP),
    ('SubmitSm', SUBMIT_SM),
    ('SubmitSm with payload', SUBMIT_SM_WITH_PAYLOAD),
    ('SubmitSm with opt params', SUBMIT_SM_WITH_OPT_PARAMS),
    ('SubmitSmResp', SubmitSmResp(1, message_id='FE456A00')),
    ('DeliverSm', DELIVER_SM),
    ('DeliverSmResp', DeliverSmResp(1)),
    ('EnquireLink', EnquireLink(1)),
    ('EnquireLinkResp', EnquireLinkResp(1)),
    ('Unbind', Unbind(1)),
    ('UnbindResp', UnbindResp(1)),
    ('GenericNack', GenericNack(1)),
]


@pytest.mark.parametrize('desc,message', TEST_MESSAGES)
def test_pdu_serialization(desc: str, message: SmppMessage):
    pdu: bytes = message.pdu()
    header: PduHeader = SmppMessage.parse_header(pdu)
    decoded_message: SmppMessage = message.__class__.from_pdu(pdu, header, DEFAULT_ENCODING)
    assert message == decoded_message, desc + ' incorrectly decoded from PDU'


@pytest.mark.parametrize('desc,message', TEST_MESSAGES)
def test_json_serialization(desc: str, message: SmppMessage):
    json_data: str = json_encode(message)
    decoded_message: SmppMessage = json_decode(json_data)
    assert message == decoded_message, desc + ' incorrectly decoded from JSON'

def test_delivery_receipt():
    msg_id: str = 'FE456A00'
    # Only minute resolution supported
    test_date: datetime = datetime.now().replace(second=0, microsecond=0)
    test_date_str: str = test_date.strftime('%y%m%d%H%M')
    stat: str = 'DELIVRD'
    text: str = '????????????????????'

    receipt: Dict[str, Any] = {
        'id': msg_id,
        'sub': 1,
        'dlvrd': 1,
        'submit date': test_date,
        'done date': test_date,
        'stat': stat,
        'err': 0,
        'text': text,
    }
    receipt_text: str = (f'id:{msg_id} sub:001 dlvrd:001 submit date:{test_date_str} '
                         f'done date:{test_date_str} stat:{stat} err:000 Text:{text}')

    deliver_sm_receipt: DeliverSm = DeliverSm(
        source=PhoneNumber('INFO', TON.ALPHANUMERIC),
        destination=PhoneNumber('+123135654618'),
        sequence_num=1,
        esm_class=0b00000100,
        short_message=receipt_text,
    )
    assert deliver_sm_receipt.parse_receipt() == receipt
    assert DeliverSm.encode_receipt(receipt) == receipt_text


class BadArg:
    pass


DELIVER_SM_PARAMS: Tuple[str, ...] = (
    'sequence_num',
    'log_id',
    'extra_data',
    'short_message',
    'source',
    'destination',
    'service_type',
    'esm_class',
    'protocol_id',
    'priority_flag',
    'schedule_delivery_time',
    'validity_period',
    'registered_delivery',
    'replace_if_present_flag',
    'encoding',
    'sm_default_msg_id',
    'message_payload',
    'optional_params',
    'auto_message_payload',
    'error_handling',
)


@pytest.mark.parametrize('param', DELIVER_SM_PARAMS)
def test_bad_args(param: str):
    _all_args = {
        'short_message': 'Hello, thanks for shopping with us.',
        'source': PhoneNumber('254722111111'),
        'destination': PhoneNumber('254722999999'),
    }
    _all_args[param] = BadArg()
    with pytest.raises(ValueError):
        DeliverSm(**_all_args)


@pytest.mark.parametrize('tag', OptionalTag.__members__.values())
def test_optional_param(tag: OptionalTag):
    with pytest.raises(ValueError):
        OptionalParam(BadArg(), '') # type: ignore

    with pytest.raises(ValueError):
        OptionalParam(tag, BadArg()) # type: ignore

    if tag == OptionalTag.MESSAGE_PAYLOAD:
        # MESSAGE_PAYLOAD param should not be instantiable, it is handled separately
        with pytest.raises(ValueError):
            OptionalParam(tag, tag.data_type())
    else:
        assert OptionalParam(tag, tag.data_type()) is not None
