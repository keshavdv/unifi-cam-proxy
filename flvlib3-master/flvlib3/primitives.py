"""
The internal FLV representations of numbers.
"""
from typing import BinaryIO
from struct import pack, unpack, error

__all__ = [
    'get_ui32', 'make_ui32',
    'get_si32_extended', 'make_si32_extended',
    'get_ui24', 'make_ui24',
    'get_ui16', 'make_ui16',
    'get_si16', 'make_si16',
    'get_ui8', 'make_ui8',
    'get_double', 'make_double'
]


# UI32
def get_ui32(stream: BinaryIO) -> int:
    try:
        ret = unpack('>I', stream.read(4))[0]
    except error:
        raise EOFError
    return ret


def make_ui32(num: int) -> bytes:
    return pack('>I', num)


# SI32 extended
def get_si32_extended(stream: BinaryIO) -> int:
    # The last 8 bits are the high 8 bits of the whole number
    # That's how Adobe likes it. Go figure...
    low_high = stream.read(4)
    if len(low_high) < 4:
        raise EOFError
    combined = low_high[3:] + low_high[:3]
    return unpack('>i', combined)[0]


def make_si32_extended(num: int) -> bytes:
    ret = pack('>i', num)
    return ret[1:] + ret[:1]


# UI24
def get_ui24(stream: BinaryIO) -> int:
    try:
        high, low = unpack('>BH', stream.read(3))
    except error:
        raise EOFError
    ret = (high << 16) + low
    return ret


def make_ui24(num: int) -> bytes:
    ret = pack('>I', num)
    return ret[1:]


# UI16
def get_ui16(stream: BinaryIO) -> int:
    try:
        ret = unpack('>H', stream.read(2))[0]
    except error:
        raise EOFError
    return ret


def make_ui16(num: int) -> bytes:
    return pack('>H', num)


# SI16
def get_si16(stream: BinaryIO) -> int:
    try:
        ret = unpack('>h', stream.read(2))[0]
    except error:
        raise EOFError
    return ret


def make_si16(num: int) -> bytes:
    return pack('>h', num)


# UI8
def get_ui8(stream: BinaryIO) -> int:
    try:
        ret = unpack('B', stream.read(1))[0]
    except error:
        raise EOFError
    return ret


def make_ui8(num: int) -> bytes:
    return pack('B', num)


# DOUBLE
def get_double(stream: BinaryIO) -> float:
    data = stream.read(8)
    try:
        ret = unpack('>d', data)[0]
    except error:
        raise EOFError
    return ret


def make_double(num: float) -> bytes:
    return pack('>d', num)
