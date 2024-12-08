from codecs import CodecInfo
from typing import List, Tuple
import pytest
from aiosmpplib import SmppDataCoding
from aiosmpplib.codec import find_codec_info


SMPP_ENCODINGS: List[str] = [coding for coding in SmppDataCoding.__members__
                             if not coding.startswith('octet_unspecified')]


@pytest.mark.parametrize('encoding', SMPP_ENCODINGS)
def test_smpp_encodings(encoding: str):
    if encoding.startswith('octet_unspecified'): # Non-existing encodings
        return
    text: str = 'Some text'
    codec_info: CodecInfo = find_codec_info(encoding, None)
    octets: bytes = codec_info.encode(text, 'strict')[0]
    string: str = codec_info.decode(octets, 'strict')[0]
    assert string == text


@pytest.mark.parametrize('encoding', SMPP_ENCODINGS)
def test_bad_arg(encoding: str):
    text: str = 'Some text'
    octets: bytes = b'Some bytes'
    codec_info: CodecInfo = find_codec_info(encoding, None)
    with pytest.raises(TypeError):
        codec_info.decode(text) # type: ignore
    if encoding not in ('euc_kr', 'iso2022_jp', 'iso2022jp', 'shift_jis'):
        # Some codecs convert any input to str, for whatever reason
        with pytest.raises(TypeError):
            codec_info.encode(octets) # type: ignore


TEST_STRING: str = 'Hülk'
TEST_DATA: List[Tuple[str, bytes]] = [
    ('utf-8', b'H\xc3\xbclk'),
    ('utf-16be', b'\x00H\x00\xfc\x00l\x00k'),
    ('ucs2', b'\x00H\x00\xfc\x00l\x00k'),
    ('gsm0338', b'H\x7elk'),
    ('gsm0338_packed', b'H?{\r'),
]


@pytest.mark.parametrize('encoding,octets', TEST_DATA)
def test_main_codecs(encoding: str, octets: bytes):
    codec_info: CodecInfo = find_codec_info(encoding, None)
    assert codec_info.encode(TEST_STRING)[0] == octets


GSM_TEST_STRING: str = 'Zoë'


def test_gsm0338_strict():
    codec_info: CodecInfo = find_codec_info('gsm0338')
    with pytest.raises(UnicodeEncodeError):
        codec_info.encode(GSM_TEST_STRING, 'strict')
    with pytest.raises(UnicodeDecodeError):
        codec_info.decode(GSM_TEST_STRING.encode('utf-8'), 'strict')


def test_gsm0338_ignore():
    codec_info: CodecInfo = find_codec_info('gsm0338')
    assert codec_info.encode(GSM_TEST_STRING, 'ignore')[0] == b'Zo'
    assert codec_info.decode(GSM_TEST_STRING.encode('utf-8'), 'ignore')[0] == 'Zo'


def test_gsm0338_replace():
    codec_info: CodecInfo = find_codec_info('gsm0338')
    assert codec_info.encode(GSM_TEST_STRING, 'replace')[0] == b'Zo?'
    assert codec_info.decode(GSM_TEST_STRING.encode('utf-8'), 'replace')[0] == 'Zo??'


def test_gsm0338_extended():
    codec_info: CodecInfo = find_codec_info('gsm0338')
    text: str = 'foo €'
    octets: bytes = b'\x66\x6f\x6f\x20\x1b\x65'
    assert codec_info.encode(text)[0] == octets
    assert codec_info.decode(octets)[0] == text
