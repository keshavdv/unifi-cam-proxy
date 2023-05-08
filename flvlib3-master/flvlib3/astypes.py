"""
The AS types and their FLV representations.
"""
from typing import BinaryIO, AnyStr, Any, List, Tuple, Dict
import os
import calendar
import datetime
import logging

from .constants import *
from .helpers import utc
from .primitives import *

__all__ = [
    'MalformedFLV',
    'as_type_to_getter_and_maker', 'type_to_as_type',
    'ECMAArray', 'FLVObject', 'MovieClip', 'Undefined', 'Reference',
    'get_number', 'make_number',
    'get_boolean', 'make_boolean',
    'make_string', 'get_string',
    'make_long_string', 'get_long_string',
    'get_ecma_array', 'make_ecma_array',
    'get_strict_array', 'make_strict_array',
    'get_date', 'make_date',
    'get_null', 'make_null',
    'get_object', 'make_object',
    'get_movie_clip', 'make_movie_clip',
    'get_undefined', 'make_undefined',
    'get_reference', 'make_reference',
    'get_script_data_variable', 'make_script_data_variable',
    'get_script_data_value', 'make_script_data_value'
]

logger = logging.getLogger('flvlib3.astypes')


class MalformedFLV(Exception):
    ...


# Number
def get_number(stream: BinaryIO, max_offset: int = None) -> float:
    return get_double(stream)


def make_number(number: float) -> bytes:
    return make_double(number)


# Boolean
def get_boolean(stream: BinaryIO, max_offset: int = None) -> bool:
    value = get_ui8(stream)
    return bool(value)


def make_boolean(value: bool) -> bytes:
    return make_ui8(bool(value))


# String
def get_string(stream: BinaryIO, max_offset: int = None) -> bytes:
    # First 16 bits are the string's length
    length = get_ui16(stream)
    # Then comes the string itself
    ret = stream.read(length)
    return ret


def make_string(string: AnyStr) -> bytes:
    if isinstance(string, str):
        # We need a blob, not unicode.
        string = string.encode()
    length = make_ui16(len(string))
    return length + string


# Long String
def get_long_string(stream: BinaryIO, max_offset: int = None) -> bytes:
    # First 32 bits are the string's length
    length = get_ui32(stream)
    # Then comes the string itself
    ret = stream.read(length)
    return ret


def make_long_string(string: AnyStr) -> bytes:
    if isinstance(string, str):
        # We need a blob, not unicode.
        string = string.encode()
    length = make_ui32(len(string))
    return length + string


# ECMA array
class ECMAArray(dict):
    ...


def get_ecma_array(stream: BinaryIO, max_offset=None) -> ECMAArray:
    length = get_ui32(stream)
    logger.debug('The ECMA array has approximately %d elements', length)
    array = ECMAArray()
    while True:
        if max_offset and (stream.tell() == max_offset):
            logger.debug('Prematurely terminating reading an ECMA array')
            break
        marker = get_ui24(stream)
        if marker == 9:
            logger.debug('Marker!')
            break
        else:
            stream.seek(-3, os.SEEK_CUR)
        name, value = get_script_data_variable(stream, max_offset=max_offset)
        array[name] = value
    return array


def make_ecma_array(d: Dict[AnyStr, Any]) -> bytes:
    length = make_ui32(len(d))
    rest = b''.join(make_script_data_variable(name, value) for name, value in d.items())
    marker = make_ui24(9)
    return length + rest + marker


# Strict array
def get_strict_array(stream: BinaryIO, max_offset: bool = None) -> List[Any]:
    length = get_ui32(stream)
    logger.debug('Strict array length = %d', length)
    elements = [get_script_data_value(stream, max_offset=max_offset) for _ in range(length)]
    return elements


def make_strict_array(array: List[Any]) -> bytes:
    length = make_ui32(len(array))
    rest = b''.join(make_script_data_value(value) for value in array)
    return length + rest


# Date
def get_date(stream: BinaryIO, max_offset: bool = None) -> datetime.datetime:
    timestamp = get_number(stream) / 1000
    # From the following document:
    #   http://opensource.adobe.com/wiki/download/
    #   attachments/1114283/amf0_spec_121207.pdf
    #
    # Section 2.13 Date Type
    #
    # (...) While the design of this type reserves room for time zone offset
    # information, it should not be filled in, nor used (...)
    _ignored = get_si16(stream)
    return datetime.datetime.fromtimestamp(timestamp, utc)


def make_date(date: datetime.datetime) -> bytes:
    if date.tzinfo:
        utc_date = date.astimezone(utc)
    else:
        # assume it's UTC
        utc_date = date.replace(tzinfo=utc)
    timestamp = make_number(calendar.timegm(utc_date.timetuple()) * 1000)
    offset = 0
    return timestamp + make_si16(offset)


# Null
def get_null(stream: BinaryIO, max_offset: bool = None) -> None:
    return None


def make_null(stream: BinaryIO) -> bytes:
    return b''


# Object
class FLVObject(dict):
    ...


def get_object(stream: BinaryIO, max_offset: bool = None) -> FLVObject:
    ret = FLVObject()
    while True:
        if max_offset and (stream.tell() == max_offset):
            logger.debug('Prematurely terminating reading an object')
            break
        marker = get_ui24(stream)
        if marker == 9:
            logger.debug('Marker!')
            break
        else:
            stream.seek(-3, os.SEEK_CUR)
        name, value = get_script_data_variable(stream)
        ret[name] = value
    return ret


def make_object(obj: FLVObject) -> bytes:
    # If the object is iterable, serialize keys/values. If not, fall back on iterating over __dict__.
    # This makes sure that make_object(get_object(StringIO(blob))) == blob
    try:
        iterator = obj.items()
    except AttributeError:
        iterator = obj.__dict__.items()
    ret = b''.join([make_script_data_variable(name, value) for name, value in iterator])
    marker = make_ui24(9)
    return ret + marker


# Movie clip
class MovieClip:
    path: bytes

    def __init__(self, path: bytes):
        self.path = path

    def __eq__(self, other):
        return isinstance(other, MovieClip) and self.path == other.path

    def __repr__(self):
        return '<MovieClip at %s>' % self.path


def get_movie_clip(stream: BinaryIO, max_offset: bool = None) -> MovieClip:
    ret = get_string(stream)
    return MovieClip(ret)


def make_movie_clip(clip: MovieClip) -> bytes:
    return make_string(clip.path)


# Undefined
class Undefined:

    def __eq__(self, other):
        return isinstance(other, Undefined)

    def __repr__(self):
        return '<Undefined>'


def get_undefined(stream: BinaryIO, max_offset: bool = None) -> Undefined:
    return Undefined()


def make_undefined(stream: BinaryIO) -> bytes:
    return b''


# Reference
class Reference:
    ref: int

    def __init__(self, ref: int):
        self.ref = ref

    def __eq__(self, other):
        return isinstance(other, Reference) and self.ref == other.ref

    def __repr__(self):
        return '<Reference to %d>' % self.ref


def get_reference(stream: BinaryIO, max_offset: bool = None) -> Reference:
    ret = get_ui16(stream)
    return Reference(ret)


def make_reference(reference: Reference) -> bytes:
    return make_ui16(reference.ref)


as_type_to_getter_and_maker = {
    VALUE_TYPE_NUMBER: (get_number, make_number),
    VALUE_TYPE_BOOLEAN: (get_boolean, make_boolean),
    VALUE_TYPE_STRING: (get_string, make_string),
    VALUE_TYPE_OBJECT: (get_object, make_object),
    VALUE_TYPE_MOVIE_CLIP: (get_movie_clip, make_movie_clip),
    VALUE_TYPE_NULL: (get_null, make_null),
    VALUE_TYPE_UNDEFINED: (get_undefined, make_undefined),
    VALUE_TYPE_REFERENCE: (get_reference, make_reference),
    VALUE_TYPE_ECMA_ARRAY: (get_ecma_array, make_ecma_array),
    VALUE_TYPE_STRICT_ARRAY: (get_strict_array, make_strict_array),
    VALUE_TYPE_DATE: (get_date, make_date),
    VALUE_TYPE_LONG_STRING: (get_long_string, make_long_string)
}

type_to_as_type = {
    bool: VALUE_TYPE_BOOLEAN,
    int: VALUE_TYPE_NUMBER,
    float: VALUE_TYPE_NUMBER,
    # WARNING: not supporting long strings here.
    # With a max length of 65535 chars, no one will notice.
    str: VALUE_TYPE_STRING,
    bytes: VALUE_TYPE_STRING,
    bytearray: VALUE_TYPE_STRING,
    list: VALUE_TYPE_STRICT_ARRAY,
    dict: VALUE_TYPE_ECMA_ARRAY,
    ECMAArray: VALUE_TYPE_ECMA_ARRAY,
    datetime.datetime: VALUE_TYPE_DATE,
    Undefined: VALUE_TYPE_UNDEFINED,
    MovieClip: VALUE_TYPE_MOVIE_CLIP,
    Reference: VALUE_TYPE_REFERENCE,
    type(None): VALUE_TYPE_NULL
}


# Script Data Variable
def get_script_data_variable(stream: BinaryIO, max_offset: bool = None) -> Tuple[AnyStr, Any]:
    name = get_string(stream)
    logger.debug('Script data name = %s', name)
    value = get_script_data_value(stream, max_offset=max_offset)
    logger.debug('Script data value = %r', value)
    return name, value


def make_script_data_variable(name: AnyStr, value: AnyStr) -> bytes:
    logger.debug('Script data name = %s', name)
    logger.debug('Script data value = %r', value)
    ret = make_string(name) + make_script_data_value(value)
    return ret


# Script Data Value
def get_script_data_value(stream: BinaryIO, max_offset: bool = None) -> Any:
    value_type = get_ui8(stream)
    logger.debug('Script data value type = %r', value_type)
    try:
        get_value = as_type_to_getter_and_maker[value_type][0]
    except KeyError:
        raise MalformedFLV('Invalid script data value type: %d' % value_type)
    logger.debug('Getter function = %r', get_value)
    value = get_value(stream, max_offset=max_offset)
    return value


def make_script_data_value(value: Any) -> bytes:
    value_type = type_to_as_type.get(type(value), VALUE_TYPE_OBJECT)
    logger.debug('Script data value type = %r', value_type)
    #  KeyError can't happen here, because we always fall back on
    #  VALUE_TYPE_OBJECT when determining value_type
    make_value = as_type_to_getter_and_maker[value_type][1]
    logger.debug('Maker function = %r', make_value)
    type_tag = make_ui8(value_type)
    ret = make_value(value)
    return type_tag + ret
