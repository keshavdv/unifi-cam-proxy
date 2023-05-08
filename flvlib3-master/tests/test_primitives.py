from io import BytesIO

from flvlib3.primitives import *


def test_ui32():
    assert get_ui32(BytesIO(b'\x02\x93\xd3\xde')) == 43242462
    assert make_ui32(3426345) == b'\x00\x34\x48\x29'


def test_si32_extended():
    assert get_si32_extended(BytesIO(b'\xcc\xff\x1b\xff')) == -3342565
    assert make_si32_extended(9823) == b'\x00\x26\x5f\x00'


def test_ui24():
    assert get_ui24(BytesIO(b'\x00\x04\xd2')) == 1234
    assert make_ui24(4321) == b'\x00\x10\xe1'


def test_ui16():
    assert get_ui16(BytesIO(b'\x00\x42')) == 66
    assert make_ui16(333) == b'\x01\x4d'


def test_si16():
    assert get_si16(BytesIO(b'\x0d\xd8')) == 3544
    assert make_si16(-24) == b'\xff\xe8'


def test_ui8():
    assert get_ui8(BytesIO(b'\x22')) == 34
    assert make_ui8(58) == b'\x3a'


def test_double():
    assert get_double(BytesIO(b'\xbf\xd4\xdd\x2f\x1a\x9f\xbe\x77')) == -0.326
    assert make_double(324653.45) == b'\x41\x13\xd0\xb5\xcc\xcc\xcc\xcd'
