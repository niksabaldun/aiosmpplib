import pytest
from typing import List, Optional, Type
from aiosmpplib.state import PduHeader, SmppCommand
from aiosmpplib.correlator import STATUS_FAILED, STATUS_SENDING, STATUS_SENT, SimpleCorrelator
from aiosmpplib.protocol import (
    DEFAULT_ENCODING,
    MESSAGE_TYPE_MAP,
    DeliverSm,
    GenericNack,
    SmppMessage,
    SubmitSm,
    SubmitSmResp,
)


FRAGMENTED_SM: List[str] = [
    ('000000ce00000005000000000000000b000000494e464f0000002B3338353939393939393939390040000000'
        '3234313132313039343035313230342b00010008008c050003350601006a0061006b006f0020006a0061006b'
        '006f0020006a0061006b006f0020006a0061006b006f0020006a0061006b006f0020006a0061006b006f0020'
        '006a0061006b006f0020006a0061006b006f0020006a0061006b006f0020006a0061006b006f0020006a0061'
        '006b006f0020006a0061006b006f0020006a0061006b006f0020006a0061'),
    ('000000ce00000005000000000000000c000000494e464f0000002B3338353939393939393939390040000000'
        '3234313132313039343035313230342b00010008008c050003350602006b006f0020006a0061006b006f0020'
        '006400750067006100200070006f00720075006b00610020010d010701610111017e010c010601600110017d'
        '0020d83dde07d83edd76d83edd70d83dde07d83edd76d83edd70d83dde07d83edd76d83edd70d83dde07d83e'
        'dd76d83edd70d83dde07d83edd76d83edd70d83dde07d83edd76d83edd70'),
    ('000000cc00000005000000000000000d000000494e464f0000002B3338353939393939393939390040000000'
        '3234313132313039343035313230342b00010008008a050003350603d83dde07d83edd76d83edd70d83dde07'
        'd83edd76d83edd70d83dde07d83edd76d83edd70d83dde07d83edd76d83edd70d83dde07d83edd76d83edd70'
        'd83dde07d83edd76d83edd70d83dde07d83edd76d83edd70d83dde07d83edd76d83edd70d83dde07d83edd76'
        'd83edd70d83dde07d83edd76d83edd70d83dde07d83edd76d83edd70'),
    ('000000cc00000005000000000000000e000000494e464f0000002B3338353939393939393939390040000000'
        '3234313132313039343035313230342b00010008008a050003350604d83dde07d83edd76d83edd70d83dde07'
        'd83edd76d83edd70d83dde07d83edd76d83edd70d83dde07d83edd76d83edd70d83dde07d83edd76d83edd70'
        'd83dde07d83edd76d83edd70d83dde07d83edd76d83edd70d83dde07d83edd76d83edd70d83dde07d83edd76'
        'd83edd70d83dde07d83edd76d83edd70d83dde07d83edd76d83edd70'),
    ('000000cc00000005000000000000000f000000494e464f0000002B3338353939393939393939390040000000'
        '3234313132313039343035313230342b00010008008a050003350605d83dde07d83edd76d83edd70d83dde07'
        'd83edd76d83edd70d83dde07d83edd76d83edd70d83dde07d83edd76d83edd70d83dde07d83edd76d83edd70'
        'd83dde07d83edd76d83edd70d83dde07d83edd76d83edd70d83dde07d83edd76d83edd70d83dde07d83edd76'
        'd83edd70d83dde07d83edd76d83edd70d83dde07d83edd76d83edd70'),
    ('00000054000000050000000000000010000000494e464f0000002B3338353939393939393939390040000000'
        '3234313132313039343035313230342b000100080012050003350606d83dde07d83edd76d83edd70'),
]
FRAGMENTED_SM_RESP: List[str] = [
    ('0000001b80000004000000000000000b4237464530303034303000'),
    ('0000001980000004000000000000000c353833423030303300'),
    ('0000001980000004000000000000000d374235343030303100'),
    ('0000001980000004000000000000000e343339393030303000'),
    ('0000001980000004000000000000000f364631413030303200'),
    ('00000019800000040000000000000010413441373030303500'),
]
FAILED_FRAGMENTED_SM_RESP: List[str] = [
    ('0000001b80000004000000000000000b4237464530303034303000'),
    ('0000001980000004000000000000000c353833423030303300'),
    ('0000001980000004000000000000000d374235343030303100'),
    ('0000001080000000000000000000000e'),  # Generic NACK
    ('0000001980000004000000000000000f364631413030303200'),
    ('00000019800000040000000000000010413441373030303500'),
]
FRAGMENTED_REPORTS: List[str] = [
    ('00000096000000050000000000ADD937000000333835393939393939393939000000494E464F000400030000000'
     '000006869643A42374645303030343030207375623A30303120646C7672643A303031207375626D697420646174'
     '653A3234313031313134353620646F6E6520646174653A3234313031313134353620737461743a44454c4956524'
     '4206572723a30303020746578743a2d20'),
    ('00000094000000050000000000ADD938000000333835393939393939393939000000494E464F000400030000000'
     '000006669643A3538334230303033207375623A30303120646C7672643A303031207375626D697420646174653A'
     '3234313031313134353620646F6E6520646174653A3234313031313134353620737461743a44454c49565244206'
     '572723a30303020746578743a2d20'),
    ('00000094000000050000000000ADD939000000333835393939393939393939000000494E464F000400030000000'
     '000006669643A3742353430303031207375623A30303120646C7672643A303031207375626D697420646174653A'
     '3234313031313134353620646F6E6520646174653A3234313031313134353620737461743a44454c49565244206'
     '572723a30303020746578743a2d20'),
    ('00000094000000050000000000ADD93a000000333835393939393939393939000000494E464F000400030000000'
     '000006669643A3433393930303030207375623A30303120646C7672643A303031207375626D697420646174653A'
     '3234313031313134353620646F6E6520646174653A3234313031313134353620737461743a44454c49565244206'
     '572723a30303020746578743a2d20'),
    ('00000094000000050000000000ADD93b000000333835393939393939393939000000494E464F000400030000000'
     '000006669643A3646314130303032207375623A30303120646C7672643A303031207375626D697420646174653A'
     '3234313031313134353620646F6E6520646174653A3234313031313134353620737461743a44454c49565244206'
     '572723a30303020746578743a2d20'),
    ('00000094000000050000000000ADD93c000000333835393939393939393939000000494E464F000400030000000'
     '000006669643A4134413730303035207375623A30303120646C7672643A303031207375626D697420646174653A'
     '3234313031313134353620646F6E6520646174653A3234313031313134353620737461743a44454c49565244206'
     '572723a30303020746578743a2d20'),
]

@pytest.mark.asyncio
async def test_fragmented_submit():
    correlator: SimpleCorrelator = SimpleCorrelator('test')
    segment_count: int = len(FRAGMENTED_SM)
    submit_sms: List[SubmitSm] = []
    for index in range(segment_count):
        # Convert DELIVER_SM to SUBMIT_SM
        pdu: bytes = bytes.fromhex(FRAGMENTED_SM[index].replace('00000005', '00000004'))
        header: PduHeader = SmppMessage.parse_header(pdu)
        submit_sm: SmppMessage = SubmitSm.from_pdu(pdu, header, DEFAULT_ENCODING)
        assert isinstance(submit_sm, SubmitSm)
        await correlator.put(submit_sm)
        submit_sms.append(submit_sm)
    for index in range(segment_count):
        pdu = bytes.fromhex(FRAGMENTED_SM_RESP[index])
        header = SmppMessage.parse_header(pdu)
        submit_sm_resp: SmppMessage = SubmitSmResp.from_pdu(pdu, header, DEFAULT_ENCODING)
        assert isinstance(submit_sm_resp, SubmitSmResp)
        original_message: Optional[SmppMessage] = await correlator.get(
            SmppCommand.SUBMIT_SM, submit_sm_resp
        )
        assert original_message is submit_sms[index]
        await correlator.put_delivery(submit_sm_resp.message_id, submit_sms[index])
        segment_status, status_code = await correlator.get_segmented(submit_sm_resp.sequence_num)
        assert segment_status is not None
        if index < segment_count - 1:
            assert status_code == STATUS_SENDING
        else:
            assert status_code == STATUS_SENT
            assert segment_status.last_response is not None
    for index in range(segment_count):
        pdu = bytes.fromhex(FRAGMENTED_REPORTS[index])
        header = SmppMessage.parse_header(pdu)
        deliver_sm: SmppMessage = DeliverSm.from_pdu(pdu, header, DEFAULT_ENCODING)
        assert isinstance(deliver_sm, DeliverSm)
        assert deliver_sm.is_receipt()
        orig_message: Optional[SubmitSm] = await correlator.get_delivery(deliver_sm)
        assert orig_message is not None
        segment_status, status_code = await correlator.get_segmented(
            orig_message.sequence_num, remove=True
        )
        assert segment_status is not None
        if index < segment_count - 1:
            assert status_code == STATUS_SENT
        else:
            assert status_code == 0
            assert segment_status.last_receipt is not None


@pytest.mark.asyncio
async def test_failed_fragmented_submit():
    correlator: SimpleCorrelator = SimpleCorrelator('test')
    segment_count: int = len(FRAGMENTED_SM)
    submit_sms: List[SubmitSm] = []
    for index in range(segment_count):
        # Convert DELIVER_SM to SUBMIT_SM
        pdu: bytes = bytes.fromhex(FRAGMENTED_SM[index].replace('00000005', '00000004'))
        header: PduHeader = SmppMessage.parse_header(pdu)
        submit_sm: SmppMessage = SubmitSm.from_pdu(pdu, header, DEFAULT_ENCODING)
        assert isinstance(submit_sm, SubmitSm)
        await correlator.put(submit_sm)
        submit_sms.append(submit_sm)
    for index in range(segment_count):
        pdu = bytes.fromhex(FAILED_FRAGMENTED_SM_RESP[index])
        header = SmppMessage.parse_header(pdu)
        message_class: Type[SmppMessage] = MESSAGE_TYPE_MAP[header.smpp_command]
        response: SmppMessage = message_class.from_pdu(pdu, header)
        assert isinstance(response, (SubmitSmResp, GenericNack))
        original_message: Optional[SmppMessage] = await correlator.get(
            SmppCommand.SUBMIT_SM, response
        )
        assert original_message is submit_sms[index]
        if isinstance(response, SubmitSmResp):
            await correlator.put_delivery(response.message_id, submit_sms[index])
        segment_status, status_code = await correlator.get_segmented(response.sequence_num)
        assert segment_status is not None
        if index < segment_count - 1:
            assert status_code == STATUS_SENDING
        else:
            assert status_code == STATUS_FAILED
            assert segment_status.last_response is not None
            assert isinstance(segment_status.last_response, GenericNack)


@pytest.mark.asyncio
async def test_fragmented_delivery():
    correlator: SimpleCorrelator = SimpleCorrelator('test')
    segment_count: int = len(FRAGMENTED_SM)
    for index in range(segment_count):
        pdu: bytes = bytes.fromhex(FRAGMENTED_SM[index])
        header: PduHeader = SmppMessage.parse_header(pdu)
        deliver_sm: SmppMessage = DeliverSm.from_pdu(pdu, header, DEFAULT_ENCODING)
        assert isinstance(deliver_sm, DeliverSm)
        full_deliver_sm: Optional[DeliverSm] = await correlator.put_delivery_segmented(deliver_sm)
        if index < segment_count - 1:
            assert full_deliver_sm is None
        else:
            assert isinstance(full_deliver_sm, DeliverSm)
            assert full_deliver_sm.short_message == (
                'jako jako jako jako jako jako jako jako jako jako jako jako jako jako jako '
                'duga poruka čćšđžČĆŠĐŽ 😇🥶🥰😇🥶🥰😇🥶🥰😇🥶🥰😇🥶🥰😇🥶🥰😇🥶🥰😇🥶🥰'
                '😇🥶🥰😇🥶🥰😇🥶🥰😇🥶🥰😇🥶🥰😇🥶🥰😇🥶🥰😇🥶🥰😇🥶🥰😇🥶🥰😇🥶🥰😇🥶🥰'
                '😇🥶🥰😇🥶🥰😇🥶🥰😇🥶🥰😇🥶🥰😇🥶🥰😇🥶🥰😇🥶🥰😇🥶🥰😇🥶🥰😇🥶🥰😇🥶🥰'
                '😇🥶🥰😇🥶🥰😇🥶🥰😇🥶🥰😇🥶🥰😇🥶🥰😇🥶🥰😇🥶🥰'
            )
