from typing import Optional, TypeVar, BinaryIO, Iterator, Type, Union, AnyStr, Any
import os
import logging
from struct import pack, unpack

from .astypes import MalformedFLV, get_script_data_variable, make_script_data_variable
from .constants import *
from .primitives import *

__all__ = [
    'EndOfTags',
    'Tag', 'AudioTag', 'VideoTag', 'ScriptTag', 'ScriptAMF3Tag', 'FLV',
    'strict_parser', 'ensure', 'create_flv_header', 'create_flv_tag', 'create_script_tag'
]

log = logging.getLogger('flvlib3.tags')

STRICT_PARSING = False


def strict_parser(switch: Optional[bool] = None) -> bool:
    global STRICT_PARSING
    if switch is not None:
        STRICT_PARSING = switch
    return STRICT_PARSING


class EndOfTags(Exception):
    ...


T = TypeVar('T')


def ensure(value: T, expected: T, error_msg: str) -> None:
    if value == expected:
        return

    if strict_parser():
        raise MalformedFLV(error_msg)
    else:
        log.warning('Skipping non-conformant value in FLV file')


class Tag:

    def __init__(self, parent_flv: 'FLV', stream: BinaryIO):
        self.stream = stream
        self.parent_flv = parent_flv
        self.offset = None
        self.size = None
        self.timestamp = None

    def parse(self) -> None:
        stream = self.stream

        self.offset = stream.tell() - 1

        # DataSize
        self.size = get_ui24(stream)

        # Timestamp + TimestampExtended
        self.timestamp = get_si32_extended(stream)

        if self.timestamp < 0:
            log.warning('The tag at offset 0x%08X has negative timestamp: %d', self.offset, self.timestamp)

        # StreamID
        stream_id = get_ui24(stream)
        ensure(stream_id, 0, 'StreamID non zero: 0x%06X' % stream_id)

        # The rest gets parsed in the subclass, it should move stream to the
        # correct position to read PreviousTagSize
        self.parse_tag_content()

        previous_tag_size = get_ui32(stream)
        ensure(
            previous_tag_size,
            self.size + 11,
            'PreviousTagSize of %d (0x%08X) not equal to actual tag size of %d (0x%08X)' %
            (previous_tag_size, previous_tag_size,
             self.size + 11, self.size + 11)
        )

    def parse_tag_content(self) -> None:
        # By default just seek past the tag content
        self.stream.seek(self.size, os.SEEK_CUR)


class AudioTag(Tag):

    def __init__(self, parent_flv: 'FLV', stream: BinaryIO):
        super().__init__(parent_flv, stream)
        self.sound_format = None
        self.sound_rate = None
        self.sound_size = None
        self.sound_type = None
        self.aac_packet_type = None  # always None for non-AAC tags

    def parse_tag_content(self) -> None:
        stream = self.stream

        sound_flags = get_ui8(stream)
        read_bytes = 1

        self.sound_format = (sound_flags & 0xF0) >> 4
        self.sound_rate = (sound_flags & 0xC) >> 2
        self.sound_size = (sound_flags & 0x2) >> 1
        self.sound_type = sound_flags & 0x1

        if self.sound_format == SOUND_FORMAT_AAC:
            # AAC packets can be sequence headers or raw data.
            # The former contain codec information needed by the decoder to be
            # able to interpret the rest of the data.
            self.aac_packet_type = get_ui8(stream)
            read_bytes += 1
            # AAC always has sampling rate of 44 kHz
            ensure(self.sound_rate, SOUND_RATE_44_KHZ,
                   'AAC sound format with incorrect sound rate: %d' % self.sound_rate)
            # AAC is always stereo
            ensure(self.sound_type, SOUND_TYPE_STEREO,
                   'AAC sound format with incorrect sound type: %d' % self.sound_type)

        if strict_parser():
            try:
                sound_format_to_string[self.sound_format]
            except KeyError:
                raise MalformedFLV('Invalid sound format: %d' % self.sound_format)
            try:
                self.aac_packet_type and aac_packet_type_to_string[self.aac_packet_type]
            except KeyError:
                raise MalformedFLV('Invalid AAC packet type: %d' % self.aac_packet_type)

        stream.seek(self.size - read_bytes, os.SEEK_CUR)

    def __repr__(self):
        if self.offset is None:
            return '<AudioTag unparsed>'
        elif self.aac_packet_type is None:
            return ('<AudioTag at offset 0x%08X, time %d, size %d, %s>' %
                    (self.offset, self.timestamp, self.size,
                     sound_format_to_string.get(self.sound_format, '?'))
                    )
        else:
            return ('<AudioTag at offset 0x%08X, time %d, size %d, %s, %s>' %
                    (self.offset, self.timestamp, self.size,
                     sound_format_to_string.get(self.sound_format, '?'),
                     aac_packet_type_to_string.get(self.aac_packet_type, '?'))
                    )


class VideoTag(Tag):

    def __init__(self, parent_flv: 'FLV', stream: BinaryIO):
        super().__init__(parent_flv, stream)
        self.frame_type = None
        self.codec_id = None
        self.h264_packet_type = None  # Always None for non-H.264 tags

    def parse_tag_content(self) -> None:
        stream = self.stream

        video_flags = get_ui8(stream)
        read_bytes = 1

        self.frame_type = (video_flags & 0xF0) >> 4
        self.codec_id = video_flags & 0xF

        if self.codec_id == CODEC_ID_H264:
            # H.264 packets can be sequence headers, NAL units or sequence
            # ends.
            self.h264_packet_type = get_ui8(stream)
            read_bytes += 1

        if strict_parser():
            try:
                frame_type_to_string[self.frame_type]
            except KeyError:
                raise MalformedFLV('Invalid frame type: %d' % self.frame_type)
            try:
                codec_id_to_string[self.codec_id]
            except KeyError:
                raise MalformedFLV('Invalid codec ID: %d' % self.codec_id)
            try:
                self.h264_packet_type and h264_packet_type_to_string[self.h264_packet_type]
            except KeyError:
                raise MalformedFLV('Invalid H.264 packet type: %d' % self.h264_packet_type)

        stream.seek(self.size - read_bytes, os.SEEK_CUR)

    def __repr__(self):
        if self.offset is None:
            return '<VideoTag unparsed>'
        elif self.h264_packet_type is None:
            return ('<VideoTag at offset 0x%08X, time %d, size %d, %s (%s)>' %
                    (self.offset, self.timestamp, self.size,
                     codec_id_to_string.get(self.codec_id, '?'),
                     frame_type_to_string.get(self.frame_type, '?'))
                    )
        else:
            return ('<VideoTag at offset 0x%08X, time %d, size %d, %s (%s), %s>' %
                    (self.offset, self.timestamp, self.size,
                     codec_id_to_string.get(self.codec_id, '?'),
                     frame_type_to_string.get(self.frame_type, '?'),
                     h264_packet_type_to_string.get(self.h264_packet_type, '?'))
                    )


class ScriptTag(Tag):

    def __init__(self, parent_flv: 'FLV', stream: BinaryIO):
        super().__init__(parent_flv, stream)
        self.name = None
        self.variable = None

    def parse_tag_content(self) -> None:
        stream = self.stream

        # Here there's always a byte with the value of 0x02,
        # which means 'string', although the spec says NOTHING
        # about it..
        value_type = get_ui8(stream)
        ensure(value_type, 2, 'The name of a script tag is not a string')

        # Need to pass the tag end offset, because apparently YouTube
        # doesn't give a *shit* about the FLV spec and just happily
        # ends the onMetaData tag after self.size bytes, instead of
        # ending it with the *required* 0x09 marker. Bastards!

        if strict_parser():
            # If we're strict, just don't pass this info
            tag_end = None
        else:
            # 11 = tag type (1) + data size (3) + timestamp (4) + stream id (3)
            tag_end = self.offset + 11 + self.size
            log.debug('max offset is 0x%08X', tag_end)

        self.name, self.variable = get_script_data_variable(stream, max_offset=tag_end)
        log.debug('A script tag with a name of %s and value of %r', self.name, self.variable)

    def __repr__(self):
        if self.offset is None:
            return '<ScriptTag unparsed>'
        else:
            return ('<ScriptTag %s at offset 0x%08X, time %d, size %d>' %
                    (self.name, self.offset, self.timestamp, self.size))


class ScriptAMF3Tag(Tag):

    def __repr__(self):
        if self.offset is None:
            return '<ScriptAMF3Tag unparsed>'
        else:
            return ('<ScriptAMF3Tag at offset 0x%08X, time %d, size %d>' %
                    (self.offset, self.timestamp, self.size))


tag_to_class = {
    TAG_TYPE_AUDIO: AudioTag,
    TAG_TYPE_VIDEO: VideoTag,
    TAG_TYPE_SCRIPT_AMF3: ScriptAMF3Tag,
    TAG_TYPE_SCRIPT: ScriptTag,
}


class FLV:

    def __init__(self, stream: BinaryIO):
        self.stream = stream
        self.version = None
        self.has_audio = None
        self.has_video = None
        self.tags = []

    def parse_header(self) -> None:
        stream = self.stream
        stream.seek(0)

        # FLV header
        header = stream.read(3)
        if len(header) < 3:
            raise MalformedFLV('The Stream is shorter than 3 bytes')

        # Do this irrelevant of STRICT_PARSING, to catch bogus streams
        if header != b'FLV':
            raise MalformedFLV('Stream signature is incorrect: 0x%X 0x%X 0x%X' % unpack('3B', header))

        # FLV version
        self.version = get_ui8(stream)
        log.debug('FLV version is %d', self.version)

        # TypeFlags
        flags = get_ui8(stream)

        ensure(flags & 0xF8, 0, 'First TypeFlagsReserved field non zero: 0x%X' % (flags & 0xF8))
        ensure(flags & 0x2, 0, 'Second TypeFlagsReserved field non zero: 0x%X' % (flags & 0x2))

        self.has_audio = False
        self.has_video = False
        if flags & 0x4:
            self.has_audio = True
        if flags & 0x1:
            self.has_video = True

        log.debug('Stream %s audio', (self.has_audio and 'has') or 'does not have')
        log.debug('Stream %s video', (self.has_video and 'has') or 'does not have')

        header_size = get_ui32(stream)
        log.debug('Header size is %d bytes', header_size)

        stream.seek(header_size)

        tag_0_size = get_ui32(stream)
        ensure(tag_0_size, 0, 'PreviousTagSize0 non zero: 0x%08X' % tag_0_size)

    def iter_tags(self) -> Iterator[Tag]:
        self.parse_header()
        try:
            while True:
                tag = self.get_next_tag()
                yield tag
        except EndOfTags:
            pass

    def read_tags(self) -> None:
        self.tags = list(self.iter_tags())

    def get_next_tag(self) -> Tag:
        stream = self.stream

        try:
            tag_type = get_ui8(stream)
        except EOFError:
            raise EndOfTags

        tag_klass = self.tag_type_to_class(tag_type)
        tag = tag_klass(self, stream)

        tag.parse()

        return tag

    def tag_type_to_class(self, tag_type: int) -> Type[Union[AudioTag, VideoTag, ScriptAMF3Tag, ScriptTag]]:
        try:
            return tag_to_class[tag_type]
        except KeyError:
            raise MalformedFLV('Invalid tag type: %d' % tag_type)


def create_flv_header(has_audio: bool = True, has_video: bool = True) -> bytes:
    type_flags = 0
    if has_video:
        type_flags = type_flags | 0x1
    if has_audio:
        type_flags = type_flags | 0x4
    return b''.join([b'FLV', make_ui8(1), make_ui8(type_flags), make_ui32(9), make_ui32(0)])


def create_flv_tag(tag_type: int, data: bytes, timestamp: int = 0) -> bytes:
    tag_type = pack('B', tag_type)
    timestamp = make_si32_extended(timestamp)
    stream_id = make_ui24(0)

    data_size = len(data)
    tag_size = data_size + 11

    return b''.join([tag_type, make_ui24(data_size), timestamp, stream_id, data, make_ui32(tag_size)])


def create_script_tag(name: AnyStr, data: Any, timestamp=0) -> bytes:
    payload = make_ui8(2) + make_script_data_variable(name, data)
    return create_flv_tag(TAG_TYPE_SCRIPT, payload, timestamp)
