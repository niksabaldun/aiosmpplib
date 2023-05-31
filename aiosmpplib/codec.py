from codecs import (Codec, CodecInfo, lookup, utf_16_be_decode, utf_16_be_encode)
from abc import abstractmethod
from struct import pack
from typing import Dict, List, Optional, Tuple

# GSM 03.38 -> unicode
GSM_BASIC_DECODE_MAP: Dict[int, str] = {
    0x00: '\u0040',  # COMMERCIAL AT
    0x01: '\u00A3',  # POUND SIGN
    0x02: '\u0024',  # DOLLAR SIGN
    0x03: '\u00A5',  # YEN SIGN
    0x04: '\u00E8',  # LATIN SMALL LETTER E WITH GRAVE
    0x05: '\u00E9',  # LATIN SMALL LETTER E WITH ACUTE
    0x06: '\u00F9',  # LATIN SMALL LETTER U WITH GRAVE
    0x07: '\u00EC',  # LATIN SMALL LETTER I WITH GRAVE
    0x08: '\u00F2',  # LATIN SMALL LETTER O WITH GRAVE
    0x09: '\u00C7',  # LATIN CAPITAL LETTER C WITH CEDILLA
    0x0A: '\u000A',  # LINE FEED
    0x0B: '\u00D8',  # LATIN CAPITAL LETTER O WITH STROKE
    0x0C: '\u00F8',  # LATIN SMALL LETTER O WITH STROKE
    0x0D: '\u000D',  # CARRIAGE RETURN
    0x0E: '\u00C5',  # LATIN CAPITAL LETTER A WITH RING ABOVE
    0x0F: '\u00E5',  # LATIN SMALL LETTER A WITH RING ABOVE
    0x10: '\u0394',  # GREEK CAPITAL LETTER DELTA
    0x11: '\u005F',  # LOW LINE
    0x12: '\u03A6',  # GREEK CAPITAL LETTER PHI
    0x13: '\u0393',  # GREEK CAPITAL LETTER GAMMA
    0x14: '\u039B',  # GREEK CAPITAL LETTER LAMDA
    0x15: '\u03A9',  # GREEK CAPITAL LETTER OMEGA
    0x16: '\u03A0',  # GREEK CAPITAL LETTER PI
    0x17: '\u03A8',  # GREEK CAPITAL LETTER PSI
    0x18: '\u03A3',  # GREEK CAPITAL LETTER SIGMA
    0x19: '\u0398',  # GREEK CAPITAL LETTER THETA
    0x1A: '\u039E',  # GREEK CAPITAL LETTER XI
    0x1C: '\u00C6',  # LATIN CAPITAL LETTER AE
    0x1D: '\u00E6',  # LATIN SMALL LETTER AE
    0x1E: '\u00DF',  # LATIN SMALL LETTER SHARP S (German)
    0x1F: '\u00C9',  # LATIN CAPITAL LETTER E WITH ACUTE
    0x20: '\u0020',  # SPACE
    0x21: '\u0021',  # EXCLAMATION MARK
    0x22: '\u0022',  # QUOTATION MARK
    0x23: '\u0023',  # NUMBER SIGN
    0x24: '\u00A4',  # CURRENCY SIGN
    0x25: '\u0025',  # PERCENT SIGN
    0x26: '\u0026',  # AMPERSAND
    0x27: '\u0027',  # APOSTROPHE
    0x28: '\u0028',  # LEFT PARENTHESIS
    0x29: '\u0029',  # RIGHT PARENTHESIS
    0x2A: '\u002A',  # ASTERISK
    0x2B: '\u002B',  # PLUS SIGN
    0x2C: '\u002C',  # COMMA
    0x2D: '\u002D',  # HYPHEN-MINUS
    0x2E: '\u002E',  # FULL STOP
    0x2F: '\u002F',  # SOLIDUS
    0x30: '\u0030',  # DIGIT ZERO
    0x31: '\u0031',  # DIGIT ONE
    0x32: '\u0032',  # DIGIT TWO
    0x33: '\u0033',  # DIGIT THREE
    0x34: '\u0034',  # DIGIT FOUR
    0x35: '\u0035',  # DIGIT FIVE
    0x36: '\u0036',  # DIGIT SIX
    0x37: '\u0037',  # DIGIT SEVEN
    0x38: '\u0038',  # DIGIT EIGHT
    0x39: '\u0039',  # DIGIT NINE
    0x3A: '\u003A',  # COLON
    0x3B: '\u003B',  # SEMICOLON
    0x3C: '\u003C',  # LESS-THAN SIGN
    0x3D: '\u003D',  # EQUALS SIGN
    0x3E: '\u003E',  # GREATER-THAN SIGN
    0x3F: '\u003F',  # QUESTION MARK
    0x40: '\u00A1',  # INVERTED EXCLAMATION MARK
    0x41: '\u0041',  # LATIN CAPITAL LETTER A
    0x42: '\u0042',  # LATIN CAPITAL LETTER B
    0x43: '\u0043',  # LATIN CAPITAL LETTER C
    0x44: '\u0044',  # LATIN CAPITAL LETTER D
    0x45: '\u0045',  # LATIN CAPITAL LETTER E
    0x46: '\u0046',  # LATIN CAPITAL LETTER F
    0x47: '\u0047',  # LATIN CAPITAL LETTER G
    0x48: '\u0048',  # LATIN CAPITAL LETTER H
    0x49: '\u0049',  # LATIN CAPITAL LETTER I
    0x4A: '\u004A',  # LATIN CAPITAL LETTER J
    0x4B: '\u004B',  # LATIN CAPITAL LETTER K
    0x4C: '\u004C',  # LATIN CAPITAL LETTER L
    0x4D: '\u004D',  # LATIN CAPITAL LETTER M
    0x4E: '\u004E',  # LATIN CAPITAL LETTER N
    0x4F: '\u004F',  # LATIN CAPITAL LETTER O
    0x50: '\u0050',  # LATIN CAPITAL LETTER P
    0x51: '\u0051',  # LATIN CAPITAL LETTER Q
    0x52: '\u0052',  # LATIN CAPITAL LETTER R
    0x53: '\u0053',  # LATIN CAPITAL LETTER S
    0x54: '\u0054',  # LATIN CAPITAL LETTER T
    0x55: '\u0055',  # LATIN CAPITAL LETTER U
    0x56: '\u0056',  # LATIN CAPITAL LETTER V
    0x57: '\u0057',  # LATIN CAPITAL LETTER W
    0x58: '\u0058',  # LATIN CAPITAL LETTER X
    0x59: '\u0059',  # LATIN CAPITAL LETTER Y
    0x5A: '\u005A',  # LATIN CAPITAL LETTER Z
    0x5B: '\u00C4',  # LATIN CAPITAL LETTER A WITH DIAERESIS
    0x5C: '\u00D6',  # LATIN CAPITAL LETTER O WITH DIAERESIS
    0x5D: '\u00D1',  # LATIN CAPITAL LETTER N WITH TILDE
    0x5E: '\u00DC',  # LATIN CAPITAL LETTER U WITH DIAERESIS
    0x5F: '\u00A7',  # SECTION SIGN
    0x60: '\u00BF',  # INVERTED QUESTION MARK
    0x61: '\u0061',  # LATIN SMALL LETTER A
    0x62: '\u0062',  # LATIN SMALL LETTER B
    0x63: '\u0063',  # LATIN SMALL LETTER C
    0x64: '\u0064',  # LATIN SMALL LETTER D
    0x65: '\u0065',  # LATIN SMALL LETTER E
    0x66: '\u0066',  # LATIN SMALL LETTER F
    0x67: '\u0067',  # LATIN SMALL LETTER G
    0x68: '\u0068',  # LATIN SMALL LETTER H
    0x69: '\u0069',  # LATIN SMALL LETTER I
    0x6A: '\u006A',  # LATIN SMALL LETTER J
    0x6B: '\u006B',  # LATIN SMALL LETTER K
    0x6C: '\u006C',  # LATIN SMALL LETTER L
    0x6D: '\u006D',  # LATIN SMALL LETTER M
    0x6E: '\u006E',  # LATIN SMALL LETTER N
    0x6F: '\u006F',  # LATIN SMALL LETTER O
    0x70: '\u0070',  # LATIN SMALL LETTER P
    0x71: '\u0071',  # LATIN SMALL LETTER Q
    0x72: '\u0072',  # LATIN SMALL LETTER R
    0x73: '\u0073',  # LATIN SMALL LETTER S
    0x74: '\u0074',  # LATIN SMALL LETTER T
    0x75: '\u0075',  # LATIN SMALL LETTER U
    0x76: '\u0076',  # LATIN SMALL LETTER V
    0x77: '\u0077',  # LATIN SMALL LETTER W
    0x78: '\u0078',  # LATIN SMALL LETTER X
    0x79: '\u0079',  # LATIN SMALL LETTER Y
    0x7A: '\u007A',  # LATIN SMALL LETTER Z
    0x7B: '\u00E4',  # LATIN SMALL LETTER A WITH DIAERESIS
    0x7C: '\u00F6',  # LATIN SMALL LETTER O WITH DIAERESIS
    0x7D: '\u00F1',  # LATIN SMALL LETTER N WITH TILDE
    0x7E: '\u00FC',  # LATIN SMALL LETTER U WITH DIAERESIS
    0x7F: '\u00E0',  # LATIN SMALL LETTER A WITH GRAVE
}

# GSM 03.38 escaped characters -> unicode
GSM_EXTENDED_DECODE_MAP: Dict[int, str] = {
    0x0A: '\u000C',  # FORM FEED
    0x14: '\u005E',  # CIRCUMFLEX ACCENT
    0x28: '\u007B',  # LEFT CURLY BRACKET
    0x29: '\u007D',  # RIGHT CURLY BRACKET
    0x2F: '\u005C',  # REVERSE SOLIDUS
    0x3C: '\u005B',  # LEFT SQUARE BRACKET
    0x3D: '\u007E',  # TILDE
    0x3E: '\u005D',  # RIGHT SQUARE BRACKET
    0x40: '\u007C',  # VERTICAL LINE
    0x65: '\u20AC',  # EURO SIGN
}

# Replacement characters, default is question mark. Used when it is not too
# important to ensure exact UTF-8 -> GSM -> UTF-8 equivalence, such as when
# humans read and write SMS. But for USSD and other M2M applications it's
# important to ensure the conversion is exact.
GSM_REPLACE_ENCODE_MAP: Dict[str, int] = {
    '\u00E7': 0x09,  # LATIN SMALL LETTER C WITH CEDILLA
    '\u0391': 0x41,  # GREEK CAPITAL LETTER ALPHA
    '\u0392': 0x42,  # GREEK CAPITAL LETTER BETA
    '\u0395': 0x45,  # GREEK CAPITAL LETTER EPSILON
    '\u0397': 0x48,  # GREEK CAPITAL LETTER ETA
    '\u0399': 0x49,  # GREEK CAPITAL LETTER IOTA
    '\u039A': 0x4B,  # GREEK CAPITAL LETTER KAPPA
    '\u039C': 0x4D,  # GREEK CAPITAL LETTER MU
    '\u039D': 0x4E,  # GREEK CAPITAL LETTER NU
    '\u039F': 0x4F,  # GREEK CAPITAL LETTER OMICRON
    '\u03A1': 0x50,  # GREEK CAPITAL LETTER RHO
    '\u03A4': 0x54,  # GREEK CAPITAL LETTER TAU
    '\u03A7': 0x58,  # GREEK CAPITAL LETTER CHI
    '\u03A5': 0x59,  # GREEK CAPITAL LETTER UPSILON
    '\u0396': 0x5A,  # GREEK CAPITAL LETTER ZETA
}

GSM_BASIC_ENCODE_MAP: Dict[str, int] = {char: code for code, char in GSM_BASIC_DECODE_MAP.items()}
GSM_EXTENDED_ENCODE_MAP: Dict[str, int] = {char: code for code, char in GSM_EXTENDED_DECODE_MAP.items()}

ESCAPE: int = 0x1B
QUESTION_MARK: int = 0x3F
NO_BREAK_SPACE: int = 0xA0


class SmsCodec(Codec):

    @classmethod
    @abstractmethod
    def get_name(cls) -> str:
        raise NotImplementedError()

    # encodings module API
    @classmethod
    def get_codec_info(cls) -> CodecInfo:
        codec: Codec = cls()
        return CodecInfo(name=cls.get_name(), encode=codec.encode, decode=codec.decode)


class GSM7BitCodec(SmsCodec):
    '''
    SMPP uses a 7-bit GSM character set.
    This class implements that encoding/decoding scheme.
    Users should never have to use this directly;
    instead, use `aiosmpplib.protocol.SubmitSm(encoding='gsm0338')`

    Example Usage:

    .. highlight:: python
    .. code-block:: python

        from aiosmpplib.codec import GSM7BitCodec

        codec = GSM7BitCodec()
        codec.encode('foo €')
    '''

    @classmethod
    def get_name(cls) -> str:
        return 'gsm0338'

    # pylint: disable=redefined-builtin; wrongly named in superclass
    def encode(self, input: str, errors: str = 'strict') -> Tuple[bytes, int]:
        if not isinstance(input, str):
            raise TypeError('Expected str input')
        if errors not in ('strict', 'replace', 'ignore'):
            raise ValueError(f'Unknown error handling {errors}.')

        gsm_codes: List[int] = self.to_gsm_codes(input, errors)
        return pack('!' + 'B' * len(gsm_codes), *gsm_codes), len(input)

    def decode(self, input: bytes, errors: str = 'strict') -> Tuple[str, int]:
        if not isinstance(input, bytes):
            raise TypeError('Expected bytes input')
        if errors not in ('strict', 'replace', 'ignore'):
            raise ValueError(f'Unknown error handling {errors}.')

        result: str = ''
        escaped: bool = False
        index: int
        byte: int
        char: str
        for index, byte in enumerate(input):
            char, escaped = self._decode_char(byte, escaped)
            if not escaped:
                if not char:
                    if errors == 'strict':
                        raise UnicodeDecodeError(self.get_name(), bytes(byte), index, index + 1,
                                                 'Unsupported character')
                    if errors == 'replace':
                        result += chr(QUESTION_MARK)
                else:
                    result += char
        consumed: int = len(input)
        if escaped:
            # Sequence ended in escape char, this should not happen
            if errors == 'strict':
                raise UnicodeDecodeError(self.get_name(), bytes(ESCAPE), consumed - 1, consumed,
                                         'Sequence ends with escape')
            if errors == 'replace':
                result += chr(NO_BREAK_SPACE)

        return result, consumed

    def _decode_char(self, char_code: int, escaped: bool) -> Tuple[str, bool]:
        if char_code == ESCAPE:
            return '', True
        if escaped:
            return GSM_EXTENDED_DECODE_MAP.get(char_code, chr(NO_BREAK_SPACE)), False
        return GSM_BASIC_DECODE_MAP.get(char_code, ''), False

    def to_gsm_codes(self, text: str, errors: str = 'strict') -> List[int]:
        gsm_codes: List[int] = []
        for pos, char in enumerate(text):
            char_code: Optional[int] = GSM_BASIC_ENCODE_MAP.get(char)
            if char_code is not None:
                gsm_codes.append(char_code)
            else:
                char_code = GSM_EXTENDED_ENCODE_MAP.get(char)
                if char_code is not None:
                    # Encode it as an escaped character
                    gsm_codes.append(ESCAPE)
                    gsm_codes.append(char_code)
                else:
                    if errors == 'strict':
                        raise UnicodeEncodeError(self.get_name(), char, pos, pos + 1, 'Unsupported char')
                    if errors == 'replace':
                        gsm_codes.append(GSM_REPLACE_ENCODE_MAP.get(char, QUESTION_MARK))
                    # Otherwise, ignore
        return gsm_codes

    @staticmethod
    def is_gsm_text(text: str) -> bool:
        '''Returns True if ``text`` can be encoded as gsm text'''
        for char in text:
            if char not in GSM_BASIC_ENCODE_MAP and char not in GSM_EXTENDED_ENCODE_MAP:
                return False

        return True


class GSM7BitPackedCodec(GSM7BitCodec):
    '''
    Packing septets to octets is required according to GSM03.38 spec,
    but uncommon in SMPP. However, some SMSC servers require it.
    '''

    @classmethod
    def get_name(cls) -> str:
        return 'gsm0338-packed'

    # pylint: disable=redefined-builtin; wrongly named in superclass
    def encode(self, input: str, errors: str = 'strict') -> Tuple[bytes, int]:
        if not isinstance(input, str):
            raise TypeError('Expected str input')
        if errors not in ('strict', 'replace', 'ignore'):
            raise ValueError(f'Unknown error handling {errors}.')

        gsm_codes: List[int] = self.to_gsm_codes(input, errors)

        # Pack septets to octets
        msg_len: int = len(gsm_codes) * 7  # Required bits
        msg_len = int(msg_len / 8) + int(msg_len % 8 > 0)  # Required bytes
        gsm_codes.append(0x00)  # Add 0x00 char for easier loop handling
        result: bytearray = bytearray(msg_len)
        count: int = 0
        index: int
        for index in range(msg_len):
            shift: int = index % 7
            lb: int = gsm_codes[count] >> shift
            hb: int = gsm_codes[count + 1] << (7 - shift) & 0xFF
            result[index] = lb + hb
            if shift == 6:
                count += 2
            else:
                count += 1

        return bytes(result), len(input)

    def decode(self, input: bytes, errors: str = 'strict') -> Tuple[str, int]:
        if not isinstance(input, bytes):
            raise TypeError('Expected bytes input')
        if errors not in ('strict', 'replace', 'ignore'):
            raise ValueError(f'Unknown error handling {errors}.')

        # Unpack septets from octets before lookup
        result: str = ''
        count: int = 0
        last: int = 0
        escaped: bool = False
        byte: int
        char: str
        for byte in input:
            mask: int = 0x7F >> count
            out: int = ((byte & mask) << count) + last
            last = byte >> (7 - count)
            char, escaped = self._decode_char(out, escaped)
            if not escaped:
                result += char
            if count == 6:
                char, escaped = self._decode_char(last, escaped)
                if not escaped:
                    result += char
                last = 0
            count = (count + 1) % 7
        consumed: int = len(input)
        if escaped:
            # Sequence ended in escape char, this should not happen
            if errors == 'strict':
                raise UnicodeDecodeError(self.get_name(), bytes(ESCAPE), consumed - 1, consumed,
                                         'Sequence ends with escape')
            if errors == 'replace':
                result += chr(NO_BREAK_SPACE)

        return result, consumed


class UCS2Codec(SmsCodec):
    '''
    This class implements the UCS2 encoding/decoding scheme.
    Users should never have to use this directly;
    instead, use `aiosmpplib.protocol.SubmitSm(encoding='ucs2')`

    UCS2 is for all intents & purposes assumed to be the same as big endian UTF16.
    '''

    @classmethod
    def get_name(cls) -> str:
        return 'ucs2'

    # pylint: disable=redefined-builtin; wrongly named in superclass
    def encode(self, input: str, errors: str = 'strict') -> Tuple[bytes, int]:
        return utf_16_be_encode(input, errors)

    def decode(self, input: bytes, errors: str = 'strict') -> Tuple[str, int]:
        return utf_16_be_decode(input, errors)


INBUILT_CODECS: Dict[str, CodecInfo] = {
    GSM7BitCodec.get_name(): GSM7BitCodec.get_codec_info(),
    GSM7BitPackedCodec.get_name(): GSM7BitPackedCodec.get_codec_info(),
    UCS2Codec.get_name(): UCS2Codec.get_codec_info(),
}


# We don't register codecs with Python registry to avoid conflict with other libraries
# which may register the same codecs. Instead, we provide our own encode and decode methods.
# We also get the ability to have per-client custom codecs.
def find_codec_info(encoding: str, custom_codecs: Optional[Dict[str, CodecInfo]] = None) -> CodecInfo:
    codec_info: Optional[CodecInfo] = None
    if custom_codecs:
        codec_info = custom_codecs.get(encoding)
    if not codec_info:
        codec_info = INBUILT_CODECS.get(encoding)
    if not codec_info:
        codec_info = lookup(encoding)  # Will raise LookupError if not found
    return codec_info
