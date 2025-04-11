from dataclasses import dataclass
from struct import pack
from enum import IntEnum, auto
from typing import Dict, Type, Union
from .utils import check_param


# SMPP optional tag constants. See section 5.3.2 of SMPP ver 3.4 spec document.

# dest_addr_subunit: It is used to route messages when received by a mobile station,
#                    for example to a smart card in the mobile station
#                    or to an external device connected to the mobile station.
DEST_ADDR_SUBUNIT = 0x0005
# dest_network_type: It is used to indicate a network type associated with
#                    the destination address of a message.
DEST_NETWORK_TYPE = 0x0006
# dest_bearer_type: It is is used to request the desired bearer
#                   for delivery of the message to the destination address.
DEST_BEARER_TYPE = 0x0007
# dest_telematics_id: It defines the telematic interworking to be used
#                     by the delivering system for the destination address.
DEST_TELEMATICS_ID = 0x0008
# source_addr_subunit: It is used to indicate where a message originated in the
#                      mobile station, for example a smart card in the mobile station
#                      or an external device connected to the mobile station.
SOURCE_ADDR_SUBUNIT = 0x000D
# source_network_type: It is used to indicate the network type associated with
#                      the device that originated the message.
SOURCE_NETWORK_TYPE = 0x000E
# source_bearer_type: It indicates the wireless bearer over which the message originated.
SOURCE_BEARER_TYPE = 0x000F
# source_telematics_id: It indicates the type of telematics interface
#                       over which the message originated.
SOURCE_TELEMATICS_ID = 0x0010
# qos_time_to_live: It defines the number of seconds which the sender requests the SMSC
#                   to keep the message if undelivered
#                   before it is deemed expired and not worth delivering.
QOS_TIME_TO_LIVE = 0x0017
# payload_type: It defines the higher layer PDU type contained in the message payload.
PAYLOAD_TYPE = 0x0019
# additional_status_info_text: It gives an ASCII textual description
#                              of the meaning of a response PDU.
ADDITIONAL_STATUS_INFO_TEXT = 0x001D
# receipted_message_id: It indicates the ID of the message being receipted
#                       in an SMSC Delivery Receipt.
RECEIPTED_MESSAGE_ID = 0x001E
# ms_msg_wait_facilities: It allows an indication to be provided to an MS that there
#                         are messages waiting for the subscriber on systems on the PLMN.
MS_MSG_WAIT_FACILITIES = 0x0030
# privacy_indicator: It indicates the privacy level of the message.
PRIVACY_INDICATOR = 0x0201
# source_subaddress: It specifies a subaddress associated with
#                    the originator of the message.
SOURCE_SUBADDRESS = 0x0202
# dest_subaddress: It specifies a subaddress associated with the destination of the message.
DEST_SUBADDRESS = 0x0203
# user_message_reference: ESME assigned message reference number.
USER_MESSAGE_REFERENCE = 0x0204
# user_response_code: It is a response code set by the user in a
#                     User Acknowledgement/Reply message.
USER_RESPONSE_CODE = 0x0205
# source_port: It is used to indicate the application port number associated with
#              the source address of the message
SOURCE_PORT = 0x020A
# destination_port: It is used to indicate the application port number associated with
#                   the destination address of the message.
DESTINATION_PORT = 0x020B
# sar_msg_ref_num: It is used to indicate the reference number for a particular
#                  concatenated short message.
SAR_MSG_REF_NUM = 0x020C
# language_indicator: It is used to indicate the language of the short message.
LANGUAGE_INDICATOR = 0x020D
# sar_total_segments: It is used to indicate the total number of short messages
#                     within the concatenated short message.
SAR_TOTAL_SEGMENTS = 0x020E
# sar_segment_seqnum: It is used to indicate the sequence number of a particular
#                     short message within the concatenated short message.
SAR_SEGMENT_SEQNUM = 0x020F
# sc_interface_version: It is used to indicate the SMPP version supported by the SMSC.
#                       It is returned in the bind response PDUs.
SC_INTERFACE_VERSION = 0x0210
# callback_num_pres_ind: It controls the presentation indication and screening of
#                        the callback number at the mobile station. f present,
#                        the :py:attr:`~callback_num` parameter must also be present.
CALLBACK_NUM_PRES_IND = 0x0302
# callback_num_atag: It associates an alphanumeric display with the call back number
CALLBACK_NUM_ATAG = 0x0303
# number_of_messages: It is used to indicate the number of messages stored in a mailbox.
NUMBER_OF_MESSAGES = 0x0304
# callback_num: It associates a call back number with the message.
CALLBACK_NUM = 0x0381
# dpf_result: It is used in the data_sm_resp PDU to indicate if delivery pending flag
#             (DPF) was set for a delivery failure of the short message.
DPF_RESULT = 0x0420
# set_dpf: An ESME may use the set_dpf parameter to request the setting of a
#          delivery pending flag (DPF) for certain delivery failure scenarios
SET_DPF = 0x0421
# ms_availability_status: It is used in the alert_notification operation to indicate
#                         the availability state of the MS to the ESME.
MS_AVAILABILITY_STATUS = 0x0422
# network_error_code: It is used to indicate the actual network error code
#                     for a delivery failure.
NETWORK_ERROR_CODE = 0x0423
# message_payload: It contains the user data.
MESSAGE_PAYLOAD = 0x0424
# delivery_failure_reason: It is used in the data_sm_resp operation to indicate the
#                          outcome of the message delivery attempt
#                          (only applicable for transaction message mode).
DELIVERY_FAILURE_REASON = 0x0425
# more_messages_to_send: It is used by the ESME in the `submit_sm` and `data_sm` operations
#                        to indicate to the SMSC that there are further messages
#                        for the same destination SME.
MORE_MESSAGES_TO_SEND = 0x0426
# message_state: It is used by the SMSC in the deliver_sm and data_sm PDUs to indicate
#                to the ESME the final message state for an SMSC Delivery Receipt.
MESSAGE_STATE = 0x0427
# ussd_service_op: It is required to define the USSD service operation when SMPP is
#                  being used as an interface to a (GSM) USSD system.
USSD_SERVICE_OP = 0x0501
# display_time: It is used to associate a display time of the short message on the MS.
DISPLAY_TIME = 0x1201
# sms_signal: It is used to provide a TDMA MS with alert tone information
#             associated with the received short message.
SMS_SIGNAL = 0x1203
# ms_validity: It is used to provide an MS with validity information
#              associated with the received short message.
MS_VALIDITY = 0x1204
# alert_on_message_delivery: It is set to instruct a MS to alert the user
#                            (in a MS implementation specific manner) when the
#                            short message arrives at the MS.
ALERT_ON_MESSAGE_DELIVERY = 0x130C
# its_reply_type: It indicates and controls the MS user's reply method to an
#                 SMS delivery message received from the ESME.
#                 It is a required parameter for the CDMA Interactive Teleservice
#                 as defined by the Korean PCS carriers [KORITS].
ITS_REPLY_TYPE = 0x1380
# its_session_info: It contains control information for the interactive session
#                   between an MS and an ESME. It is a required parameter for the CDMA
#                   Interactive Teleservice as defined by the Korean PCS carriers [KORITS].
ITS_SESSION_INFO = 0x1383


def tag_data_type(tag_code: int) -> Type:
    if tag_code in (0x0005, 0x0006, 0x0007, 0x0008, 0x000D, 0x000E, 0x000F, 0x0010, 0x0017,
                    0x0019, 0x0030, 0x0201, 0x0204, 0x0205, 0x020A, 0x020B, 0x020C, 0x020D,
                    0x020E, 0x020F, 0x0210, 0x0302, 0x0304, 0x0420, 0x0421, 0x0422, 0x0425,
                    0x0426, 0x0427, 0x1201, 0x1203, 0x1204, 0x1380):
        return int
    if tag_code == 0x130C:
        # ALERT_ON_MESSAGE_DELIVERY doesn't actually have any value.
        # We use bool to indicate whether the parameter should be set.
        return bool
    return str  # Vendor specific tags are assumed to be strings


class SmppCommand(IntEnum):
    BIND_RECEIVER = 0x00000001
    BIND_RECEIVER_RESP = 0x80000001
    BIND_TRANSMITTER = 0x00000002
    BIND_TRANSMITTER_RESP = 0x80000002
    BIND_TRANSCEIVER = 0x00000009
    BIND_TRANSCEIVER_RESP = 0x80000009
    UNBIND = 0x00000006
    UNBIND_RESP = 0x80000006
    SUBMIT_SM = 0x00000004
    SUBMIT_SM_RESP = 0x80000004
    DELIVER_SM = 0x00000005
    DELIVER_SM_RESP = 0x80000005
    ENQUIRE_LINK = 0x00000015
    ENQUIRE_LINK_RESP = 0x80000015
    GENERIC_NACK = 0x80000000
    # aiosmpplib currently does not handle the following SMPP commands.
    # Open a github issue if you require support for a command in this list.
    QUERY_SM = 0x00000003
    QUERY_SM_RESP = 0x80000003
    REPLACE_SM = 0x00000007
    REPLACE_SM_RESP = 0x80000007
    CANCEL_SM = 0x00000008
    CANCEL_SM_RESP = 0x80000008
    SUBMIT_MULTI = 0x00000021
    SUBMIT_MULTI_RESP = 0x80000021
    OUTBIND = 0x0000000B
    ALERT_NOTIFICATION = 0x00000102
    DATA_SM = 0x00000103
    DATA_SM_RESP = 0x80000103

COMMAND_RESPONSE_MAP: Dict[SmppCommand, SmppCommand] = {
    SmppCommand.BIND_RECEIVER: SmppCommand.BIND_RECEIVER_RESP,
    SmppCommand.BIND_TRANSMITTER: SmppCommand.BIND_TRANSMITTER_RESP,
    SmppCommand.BIND_TRANSCEIVER: SmppCommand.BIND_TRANSCEIVER_RESP,
    SmppCommand.UNBIND: SmppCommand.UNBIND_RESP,
    SmppCommand.SUBMIT_SM: SmppCommand.SUBMIT_SM_RESP,
    SmppCommand.DELIVER_SM: SmppCommand.DELIVER_SM_RESP,
    SmppCommand.ENQUIRE_LINK: SmppCommand.ENQUIRE_LINK_RESP,
    SmppCommand.QUERY_SM: SmppCommand.QUERY_SM_RESP,
    SmppCommand.REPLACE_SM: SmppCommand.REPLACE_SM_RESP,
    SmppCommand.CANCEL_SM: SmppCommand.CANCEL_SM_RESP,
    SmppCommand.SUBMIT_MULTI: SmppCommand.SUBMIT_MULTI_RESP,
    SmppCommand.DATA_SM: SmppCommand.DATA_SM_RESP,
}
RESPONSE_COMMAND_MAP: Dict[SmppCommand, SmppCommand] = {resp: comm for comm, resp
                                                        in COMMAND_RESPONSE_MAP.items()}

DLR_ERROR_NO_ERROR = 0
DLR_ERROR_UNKNOWN_SUBSCRIBER = 1
DLR_ERROR_ILLEGAL_SUBSCRIBER = 9
DLR_ERROR_TELESERVICE_NOT_PROVISIONED = 11
DLR_ERROR_CALL_BARRED = 13
DLR_ERROR_CUG_REJECT = 15
DLR_ERROR_NO_SMS_SUPPORT_IN_MS = 19
DLR_ERROR_ERROR_IN_MS = 20
DLR_ERROR_FACILITY_NOT_SUPPORTED = 21
DLR_ERROR_MEMORY_CAPACITY_EXCEEDED = 22
DLR_ERROR_ABSENT_SUBSCRIBER = 29
DLR_ERROR_MS_BUSY_FOR_MT_SMS = 30
DLR_ERROR_NETWORK_PROTOCOL_FAILURE = 36
DLR_ERROR_ILLEGAL_EQUIPMENT = 44
DLR_ERROR_NO_PAGING_RESPONSE = 60
DLR_ERROR_GMSC_CONGESTION = 61
DLR_ERROR_HLR_TIMEOUT = 63
DLR_ERROR_MSC_SGSN_TIMEOUT = 64
DLR_ERROR_SMRSE_TCP_ERROR = 70
DLR_ERROR_MT_CONGESTION = 72
DLR_ERROR_GPRS_SUSPENDED = 75
DLR_ERROR_NO_PAGING_RESPONSE_VIA_MSC = 80
DLR_ERROR_IMSI_DETACHED = 81
DLR_ERROR_ROAMING_RESTRICTION = 82
DLR_ERROR_DEREGISTERED_IN_HLR_FOR_GSM = 83
DLR_ERROR_PURGED_FOR_GSM = 84
DLR_ERROR_NO_PAGING_RESPONSE_VIA_SGSN = 85
DLR_ERROR_GPRS_DETACHED = 86
DLR_ERROR_DEREGISTERED_IN_HLR_FOR_GPRS = 87
DLR_ERROR_THE_MS_PURGED_FOR_GPRS = 88
DLR_ERROR_UNIDENTIFIED_SUBSCRIBER_VIA_MSC = 89
DLR_ERROR_UNIDENTIFIED_SUBSCRIBER_VIA_SGSN = 90
DLR_ERROR_ORIGINATOR_MISSING_CREDIT = 112
DLR_ERROR_DESTINATION_MISSING_CREDIT = 113
DLR_ERROR_ERROR_IN_PREPAID_SYSTEM = 114
DLR_ERROR_OTHER_ERROR = 500
DLR_ERROR_FIXNET_NOT_ALLOWED = 986
DLR_ERROR_MESSAGE_TOO_LONG = 987
DLR_ERROR_MNP_SYSTEM_ERROR = 988
DLR_ERROR_SUPPLIER_REJECTED_SMS = 989
DLR_ERROR_HLR_FAILURE = 990
DLR_ERROR_REJECTED_BY_MESSAGE_TEXT_FILTER = 991
DLR_ERROR_PORTED_NUMBERS_NOT_SUPPORTED = 992
DLR_ERROR_BLACKLISTED_SENDER = 993
DLR_ERROR_NO_CREDIT = 994
DLR_ERROR_UNDELIVERABLE = 995
DLR_ERROR_VALIDITY_EXPIRED = 996
DLR_ERROR_BLACKLISTED_RECEIVER = 997
DLR_ERROR_NO_ROUTE = 998
DLR_ERROR_REPEATED_SUBMISSION = 999

DLR_ERROR: Dict[int, str] = {
    DLR_ERROR_NO_ERROR: 'No error',
    DLR_ERROR_UNKNOWN_SUBSCRIBER: 'Unknown subscriber',
    DLR_ERROR_ILLEGAL_SUBSCRIBER: 'Illegal subscriber',
    DLR_ERROR_TELESERVICE_NOT_PROVISIONED: 'Teleservice not provisioned',
    DLR_ERROR_CALL_BARRED: 'Call barred',
    DLR_ERROR_CUG_REJECT: 'CUG reject',
    DLR_ERROR_NO_SMS_SUPPORT_IN_MS: 'No SMS support in MS',
    DLR_ERROR_ERROR_IN_MS: 'Error in MS',
    DLR_ERROR_FACILITY_NOT_SUPPORTED: 'Facility not supported',
    DLR_ERROR_MEMORY_CAPACITY_EXCEEDED: 'Memory capacity exceeded',
    DLR_ERROR_ABSENT_SUBSCRIBER: 'Absent subscriber',
    DLR_ERROR_MS_BUSY_FOR_MT_SMS: 'MS busy for MT SMS',
    DLR_ERROR_NETWORK_PROTOCOL_FAILURE: 'Network/Protocol failure',
    DLR_ERROR_ILLEGAL_EQUIPMENT: 'Illegal equipment',
    DLR_ERROR_NO_PAGING_RESPONSE: 'No paging response',
    DLR_ERROR_GMSC_CONGESTION: 'GMSC congestion',
    DLR_ERROR_HLR_TIMEOUT: 'HLR timeout',
    DLR_ERROR_MSC_SGSN_TIMEOUT: 'MSC/SGSN_timeout',
    DLR_ERROR_SMRSE_TCP_ERROR: 'SMRSE/TCP error',
    DLR_ERROR_MT_CONGESTION: 'MT congestion',
    DLR_ERROR_GPRS_SUSPENDED: 'GPRS suspended',
    DLR_ERROR_NO_PAGING_RESPONSE_VIA_MSC: 'No paging response via MSC',
    DLR_ERROR_IMSI_DETACHED: 'IMSI detached',
    DLR_ERROR_ROAMING_RESTRICTION: 'Roaming restriction',
    DLR_ERROR_DEREGISTERED_IN_HLR_FOR_GSM: 'Deregistered in HLR for GSM',
    DLR_ERROR_PURGED_FOR_GSM: 'Purged for GSM',
    DLR_ERROR_NO_PAGING_RESPONSE_VIA_SGSN: 'No paging response via SGSN',
    DLR_ERROR_GPRS_DETACHED: 'GPRS detached',
    DLR_ERROR_DEREGISTERED_IN_HLR_FOR_GPRS: 'Deregistered in HLR for GPRS',
    DLR_ERROR_THE_MS_PURGED_FOR_GPRS: 'The MS purged for GPRS',
    DLR_ERROR_UNIDENTIFIED_SUBSCRIBER_VIA_MSC: 'Unidentified subscriber via MSC',
    DLR_ERROR_UNIDENTIFIED_SUBSCRIBER_VIA_SGSN: 'Unidentified subscriber via SGSN',
    DLR_ERROR_ORIGINATOR_MISSING_CREDIT: 'Originator missing credit on prepaid account',
    DLR_ERROR_DESTINATION_MISSING_CREDIT: 'Destination missing credit on prepaid account',
    DLR_ERROR_ERROR_IN_PREPAID_SYSTEM: 'Error in prepaid system',
    DLR_ERROR_OTHER_ERROR: 'Other error',
    DLR_ERROR_FIXNET_NOT_ALLOWED: 'Fixnet not allowed',
    DLR_ERROR_MESSAGE_TOO_LONG: 'Message too long',
    DLR_ERROR_MNP_SYSTEM_ERROR: 'MNP/System error',
    DLR_ERROR_SUPPLIER_REJECTED_SMS: 'Supplier rejected SMS',
    DLR_ERROR_HLR_FAILURE: 'HLR failure',
    DLR_ERROR_REJECTED_BY_MESSAGE_TEXT_FILTER: 'Rejected by message text filter',
    DLR_ERROR_PORTED_NUMBERS_NOT_SUPPORTED: 'Ported numbers not supported on destination',
    DLR_ERROR_BLACKLISTED_SENDER: 'Blacklisted sender',
    DLR_ERROR_NO_CREDIT: 'No credit',
    DLR_ERROR_UNDELIVERABLE: 'Undeliverable',
    DLR_ERROR_VALIDITY_EXPIRED: 'Validity expired',
    DLR_ERROR_BLACKLISTED_RECEIVER: 'Blacklisted receiver',
    DLR_ERROR_NO_ROUTE: 'No route',
    DLR_ERROR_REPEATED_SUBMISSION: 'Repeated submission (possible looping)',
}

class SmppCommandStatus(IntEnum):
    '''
    Represents the various SMPP commands statuses.
    '''

    # See section 5.1.3 of SMPP ver 3.4 spec document

    ESME_ROK = 0x00000000
    ESME_RINVMSGLEN = 0x00000001
    ESME_RINVCMDLEN = 0x00000002
    ESME_RINVCMDID = 0x00000003
    ESME_RINVBNDSTS = 0x00000004
    ESME_RALYBND = 0x00000005
    ESME_RINVPRTFLG = 0x00000006
    ESME_RINVREGDLVFLG = 0x00000007
    ESME_RSYSERR = 0x00000008
    ESME_RINVSRCADR = 0x0000000A
    ESME_RINVDSTADR = 0x0000000B
    ESME_RINVMSGID = 0x0000000C
    ESME_RBINDFAIL = 0x0000000D
    ESME_RINVPASWD = 0x0000000E
    ESME_RINVSYSID = 0x0000000F
    ESME_RCANCELFAIL = 0x00000011
    ESME_RREPLACEFAIL = 0x00000013
    ESME_RMSGQFUL = 0x00000014
    ESME_RINVSERTYP = 0x00000015
    ESME_RINVNUMDESTS = 0x00000033
    ESME_RINVDLNAME = 0x00000034
    ESME_RINVDESTFLAG = 0x00000040
    ESME_RINVSUBREP = 0x00000042
    ESME_RINVESMCLASS = 0x00000043
    ESME_RCNTSUBDL = 0x00000044
    ESME_RSUBMITFAIL = 0x00000045
    ESME_RINVSRCTON = 0x00000048
    ESME_RINVSRCNPI = 0x00000049
    ESME_RINVDSTTON = 0x00000050
    ESME_RINVDSTNPI = 0x00000051
    ESME_RINVSYSTYP = 0x00000053
    ESME_RINVREPFLAG = 0x00000054
    ESME_RINVNUMMSGS = 0x00000055
    ESME_RTHROTTLED = 0x00000058
    ESME_RINVSCHED = 0x00000061
    ESME_RINVEXPIRY = 0x00000062
    ESME_RINVDFTMSGID = 0x00000063
    ESME_RX_T_APPN = 0x00000064
    ESME_RX_P_APPN = 0x00000065
    ESME_RX_R_APPN = 0x00000066
    ESME_RQUERYFAIL = 0x00000067
    ESME_RINVOPTPARSTREAM = 0x000000C0
    ESME_ROPTPARNOTALLWD = 0x000000C1
    ESME_RINVPARLEN = 0x000000C2
    ESME_RMISSINGOPTPARAM = 0x000000C3
    ESME_RINVOPTPARAMVAL = 0x000000C4
    ESME_RDELIVERYFAILURE = 0x000000FE
    ESME_RUNKNOWNERR = 0x000000FF

    @property
    def description(self) -> str:
        if self.value == 0x00000000:
            return 'Success'
        if self.value == 0x00000001:
            return 'Message Length is invalid'
        if self.value == 0x00000002:
            return 'Command Length is invalid'
        if self.value == 0x00000003:
            return 'Invalid Command ID'
        if self.value == 0x00000004:
            return 'Incorrect BIND Status for given command'
        if self.value == 0x00000005:
            return 'ESME Already in Bound State'
        if self.value == 0x00000006:
            return 'Invalid Priority Flag'
        if self.value == 0x00000007:
            return 'Invalid Registered Delivery Flag'
        if self.value == 0x00000008:
            return 'System Error'
        if self.value == 0x0000000A:
            return 'Invalid Source Address'
        if self.value == 0x0000000B:
            return 'Invalid Dest Addr'
        if self.value == 0x0000000C:
            return 'Message ID is invalid'
        if self.value == 0x0000000D:
            return 'Bind Failed'
        if self.value == 0x0000000E:
            return 'Invalid Password'
        if self.value == 0x0000000F:
            return 'Invalid System ID'
        if self.value == 0x00000011:
            return 'Cancel SM Failed'
        if self.value == 0x00000013:
            return 'Replace SM Failed'
        if self.value == 0x00000014:
            return 'Message Broker Full'
        if self.value == 0x00000015:
            return 'Invalid Service Type'
        if self.value == 0x00000033:
            return 'Invalid number of destinations'
        if self.value == 0x00000034:
            return 'Invalid Distribution List name'
        if self.value == 0x00000040:
            return 'Destination flag is invalid (submit_multi)'
        if self.value == 0x00000042:
            return 'Invalid (submit with replace) request'
        if self.value == 0x00000043:
            return 'Invalid esm_class field data'
        if self.value == 0x00000044:
            return 'Cannot Submit to Distribution List'
        if self.value == 0x00000045:
            return 'Submit_sm or submit_multi failed'
        if self.value == 0x00000048:
            return 'Invalid Source address TON'
        if self.value == 0x00000049:
            return 'Invalid Source address NPI'
        if self.value == 0x00000050:
            return 'Invalid Destination address TON'
        if self.value == 0x00000051:
            return 'Invalid Destination address NPI'
        if self.value == 0x00000053:
            return 'Invalid system_type field'
        if self.value == 0x00000054:
            return 'Invalid replace_if_present flag'
        if self.value == 0x00000055:
            return 'Invalid number of messages'
        if self.value == 0x00000058:
            return 'Throttling error (ESME has exceeded allowed message limits)'
        if self.value == 0x00000061:
            return 'Invalid Scheduled Delivery Time'
        if self.value == 0x00000062:
            return 'Invalid message validity period (Expiry time)'
        if self.value == 0x00000063:
            return 'Predefined Message Invalid or Not Found'
        if self.value == 0x00000064:
            return 'ESME Receiver Temporary App Error Code'
        if self.value == 0x00000065:
            return 'ESME Receiver Permanent App Error Code'
        if self.value == 0x00000066:
            return 'ESME Receiver Reject Message Error Code'
        if self.value == 0x00000067:
            return 'query_sm request failed'
        if self.value == 0x000000C0:
            return 'Error in the optional part of the PDU Body.'
        if self.value == 0x000000C1:
            return 'Optional Parameter not allowed'
        if self.value == 0x000000C2:
            return 'Invalid Parameter Length.'
        if self.value == 0x000000C3:
            return 'Expected Optional Parameter missing'
        if self.value == 0x000000C4:
            return 'Invalid Optional Parameter Value'
        if self.value == 0x000000FE:
            return 'Delivery Failure (used for data_sm_resp)'
        return 'Unknown Error' # self.value == 0x000000FF


class SmppSessionState(IntEnum):
    '''
    Represensts the states in which an SMPP session can be in.
    '''
    # See section 2.2 of SMPP spec document v3.4

    # An ESME has established a network connection to the SMSC
    # but has not yet issued a Bind request.
    OPEN = auto()
    # A connected ESME has requested to bind as an ESME Transmitter (by issuing a
    # bind_transmitter PDU) and has received a response from the SMSC authorising its bind request.
    BOUND_TX = auto()
    # A connected ESME has requested to bind as an ESME Receiver (by issuing a
    # bind_receiver PDU) and has received a response from the SMSC authorising its bind request.
    BOUND_RX = auto()
    # A connected ESME has requested to bind as an ESME Transceiver (by issuing a
    # bind_transceiver PDU) and has received a response from the SMSC authorising its bind request.
    BOUND_TRX = auto()
    # An ESME has unbound from the SMSC and has closed the network connection.
    # The SMSC may also unbind from the ESME.
    CLOSED = auto()


class BindMode(IntEnum):
    '''
    Represensts the ESME bind mode.
    '''
    TRANSMITTER = auto()
    RECEIVER = auto()
    TRANSCEIVER = auto()

    @property
    def smpp_command(self) -> SmppCommand:
        if self == BindMode.TRANSMITTER:
            return SmppCommand.BIND_TRANSMITTER
        if self == BindMode.RECEIVER:
            return SmppCommand.BIND_RECEIVER
        return SmppCommand.BIND_TRANSCEIVER

    @property
    def session_state(self) -> SmppSessionState:
        if self == BindMode.TRANSMITTER:
            return SmppSessionState.BOUND_TX
        if self == BindMode.RECEIVER:
            return SmppSessionState.BOUND_TX
        return SmppSessionState.BOUND_TRX

    @property
    def description(self) -> str:
        return self.name.lower()


class SmppDataCoding(IntEnum):
    '''
    Represents the various SMPP data encodings.
    '''

    # The attributes of this class are equivalent to some of the names
    # found in the python standard-encodings documentation
    # We cant use all python standard encodings[1]
    # We can only use the ones defined in SMPP spec[2];
    #
    # 1. https://docs.python.org/3/library/codecs.html#standard-encodings
    # 2. section 5.2.19 of SMPP ver 3.4 spec document.

    gsm0338 = 0b00000000
    gsm0338_packed = 0b00000000  # Non-standard
    ascii = 0b00000001
    octet_unspecified_I = 0b00000010
    latin_1 = 0b00000011
    octet_unspecified_II = 0b00000100
    # iso2022_jp, iso2022jp and iso-2022-jp are aliases
    # see: https://stackoverflow.com/a/43240579/2768067
    iso2022_jp = 0b00000101
    iso8859_5 = 0b00000110
    iso8859_8 = 0b00000111
    # see: https://stackoverflow.com/a/14488478/2768067
    ucs2 = 0b00001000
    shift_jis = 0b00001001
    iso2022jp = 0b00001010
    # reservedI = 0b00001011
    # reservedII = 0b00001100
    euc_kr = 0b00001110
    # not the same as iso2022_jp but ... ¯\_(ツ)_/¯
    # iso-2022-jp = 0b00001101, 'Extended Kanji JIS(X 0212 - 1990)'

    @property
    def description(self) -> str:
        if self.value == 0b00000000:
            return 'SMSC Default Alphabet'
        if self.value == 0b00000001:
            return 'IA5(CCITT T.50) / ASCII(ANSI X3.4)'
        if self.value == 0b00000010:
            return 'Octet unspecified(8 - bit binary)'
        if self.value == 0b00000011:
            return 'Latin 1 (ISO - 8859 - 1)'
        if self.value == 0b00000100:
            return 'Octet unspecified(8 - bit binary)'
        if self.value == 0b00000101:
            return 'JIS(X 0208 - 1990)'
        if self.value == 0b00000110:
            return 'Cyrllic(ISO - 8859 - 5)'
        if self.value == 0b00000111:
            return 'Latin / Hebrew(ISO - 8859 - 8)'
        if self.value == 0b00001000:
            return 'UCS2(ISO / IEC - 10646)'
        if self.value == 0b00001000:
            return 'UCS2(ISO / IEC - 10646)'
        if self.value == 0b00001001:
            return 'Pictogram Encoding'
        if self.value == 0b00001010:
            return 'ISO - 2022 - JP(Music Codes)'
        return 'KS C 5601' # self.value == 0b00001110


@dataclass
class OptionalParam():
    '''
    A SMPP optional parameter.

    Optional parameters MUST always appear at the end of a message,
    in the `Optional Parameters` section of the SMPP PDU.
    However, they may be included in ANY ORDER within the `Optional Parameters` section
    and NEED NOT be encoded in the order presented in the SMPP document.

    see section 5.3.2 of SMPP ver 3.4 spec document.
    '''
    tag: int
    value: Union[int, str, bool]

    # see section 5.3.2 of SMPP ver 3.4 spec document.
    # All optional parameters have the following general TLV (Tag, Length, Value) format.
    # Tag, Integer, 2octets
    # Length, Integer, 2octets
    # Value, type varies, size varies.

    # As an example, to represent a `receipted_message_id`, we need;

    # import aiosmpplib, struct
    # my_receipted_message_id = Tag + Length + Value
    # param = aiosmpplib.OptionalParam.NAME_to_TAG['receipted_message_id']
    # length = ?
    # value = 'ThisIsSomeMessageId'
    # value = Value.encode('ascii') + chr(0).encode('ascii') # since it is a c-octet string
    # length = len(value); assert length <= 65 # Value is c-octet string of size 1-65
    # tag & length are each Int, 2octet. Ints in SMPP are unsigned. Hence use '!H' in struct pack
    # my_receipted_message_id = struct.pack('!HH', tag, length) + value
    # >>> print(my_receipted_message_id)
    # b'\x00\x1e\x00\x14ThisIsSomeMessageId\x00'

    def __post_init__(self):
        check_param(self.tag, 'tag', int, maxlen=2)
        check_param(self.value, 'value', tag_data_type(self.tag))
        if self.tag == MESSAGE_PAYLOAD:
            # Special case Octet String, with same encoding as short_message
            # It can't be built here, because encoding info from both ESME and SubmitSm is needed
            raise ValueError('Creation OptionalParam with MESSAGE_PAYLOAD tag is not allowed. '
                             'It is handled automatically if needed.')

    @property
    def length(self) -> int:
        '''
        Returns the Value field of an optional SMPP parameter.
        The Length field indicates the length of the Value field in octets(integer).
        '''
        if self.tag in (
            DEST_ADDR_SUBUNIT,
            DEST_NETWORK_TYPE,
            DEST_BEARER_TYPE,
            SOURCE_ADDR_SUBUNIT,
            SOURCE_NETWORK_TYPE,
            SOURCE_BEARER_TYPE,
            SOURCE_TELEMATICS_ID,
            PAYLOAD_TYPE,
            MS_MSG_WAIT_FACILITIES,
            PRIVACY_INDICATOR,
            USER_RESPONSE_CODE,
            LANGUAGE_INDICATOR,
            SAR_TOTAL_SEGMENTS,
            SAR_SEGMENT_SEQNUM,
            SC_INTERFACE_VERSION,
            CALLBACK_NUM_PRES_IND,
            NUMBER_OF_MESSAGES,
            DPF_RESULT,
            SET_DPF,
            MS_AVAILABILITY_STATUS,
            DELIVERY_FAILURE_REASON,
            MORE_MESSAGES_TO_SEND,
            MESSAGE_STATE,
            DISPLAY_TIME,
            MS_VALIDITY,
            ITS_REPLY_TYPE
        ):
            # This is for unsigned ints size 1
            # SMPP doc says: 'Length of value part in octets'.
            return 1
        if self.tag in (
            DEST_TELEMATICS_ID,
            USER_MESSAGE_REFERENCE,
            SOURCE_PORT,
            DESTINATION_PORT,
            SAR_MSG_REF_NUM,
            SMS_SIGNAL
        ):
            return 2
        if self.tag == QOS_TIME_TO_LIVE:
            # This is for unsigned ints size 4
            return 4
        if self.tag in (ADDITIONAL_STATUS_INFO_TEXT, RECEIPTED_MESSAGE_ID):
            assert isinstance(self.value, str) # For linters
            return len(self.value) + 1 # C Octet String (+1 for null termination)
        if isinstance(self.value, str):
            return len(self.value) # Octet String (no null termination)
        # Only remaining option is alert_on_message_delivery; see section 5.3.2.41 of SMPP document
        return 0

    @property
    def tlv(self) -> bytes:
        '''
        Returns the bytes representation of an optional SMPP parameter.
        '''

        length: int = self.length
        if tag_data_type(self.tag) == int:
            int_format: Dict[int, str] = {
                1: '!HHB', # unsigned char
                2: '!HHH', # unsigned short
                4: '!HHI', # unsigned int
            }
            return pack(int_format[length], self.tag, length, self.value)
        if tag_data_type(self.tag) == str:
            assert isinstance(self.value, str) # For linters
            val: bytes = self.value.encode('ascii') # Octet String
            if self.tag in (ADDITIONAL_STATUS_INFO_TEXT, RECEIPTED_MESSAGE_ID):
                val += chr(0).encode('ascii') # C Octet String, terminate with NULL
            return pack('!HH', self.tag, length) + val
        # Only remaining option is alert_on_message_delivery; see section 5.3.2.41 of SMPP document
        if self.value:
            # TLV has no value field
            return pack('!HH', self.tag, self.length)
        return b''


class TON(IntEnum):
    '''
    Type of Number constants.
    '''

    # see section 5.2.5 of SMPP spec document v3.4
    UNKNOWN = 0b00000000
    INTERNATIONAL = 0b00000001
    NATIONAL = 0b00000010
    NETWORK_SPECIFIC = 0b00000011
    SUBSCRIBER_NUMBER = 0b00000100
    ALPHANUMERIC = 0b00000101
    ABBREVIATED = 0b00000110


class NPI(IntEnum):
    '''
    Numeric Plan Indicator constants.
    '''

    # see section 5.2.6 of SMPP spec document v3.4
    UNKNOWN = 0b00000000
    ISDN = 0b00000001
    DATA = 0b00000011
    TELEX = 0b00000100
    LAND_MOBILE = 0b00000110
    NATIONAL = 0b00001000
    PRIVATE = 0b00001001
    ERMES = 0b00001010
    INTERNET = 0b00001110
    WAP_CLIENT_ID = 0b00010010


@dataclass
class PhoneNumber():
    '''
    SMPP phone number representation.
    '''
    number: str
    ton: TON = TON.UNKNOWN
    npi: NPI = NPI.UNKNOWN

    def __post_init__(self):
        check_param(self.number, 'number', str, maxlen=20)
        check_param(self.ton, 'ton', TON)
        check_param(self.npi, 'npi', NPI)


@dataclass
class PduHeader():
    '''
    PDU header representation
    '''
    pdu_length: int # Total PDU length
    smpp_command: SmppCommand # SMPP command
    command_status: SmppCommandStatus # SMPP response status (only relevant for responses)
    sequence_num: int # SMPP sequence number


class SmppError(Exception):
    def __init__(self, smpp_command: SmppCommand, command_status: SmppCommandStatus) -> None:
        super().__init__()
        self.smpp_command: SmppCommand = smpp_command
        self.command_status: SmppCommandStatus = command_status
