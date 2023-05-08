import logging
from io import BytesIO
import pytest
from flvlib3.astypes import MalformedFLV
from flvlib3.constants import *
from flvlib3.tags import *

strict_parser(True)


class WarningCounterFilter:
    warnings = 0

    def filter(self, record):
        if record.levelno == logging.WARNING:
            self.warnings += 1
            return 0
        return 1


class FakeBytesIO(BytesIO):
    """
    A BytesIO that lies about its tell() position.
    Useful to simulate being in the middle of a file
    """

    def __init__(self, buf=b'', offset=0):
        BytesIO.__init__(self, buf)
        self.offset = offset

    def tell(self):
        return BytesIO.tell(self) + self.offset


class TestEnsure:

    def test_ensure_strict(self):
        strict_parser(True)
        with pytest.raises(MalformedFLV):
            assert ensure(1, 2, 'error')

    def test_ensure_non_strict(self):
        strict_parser(False)
        f = WarningCounterFilter()
        logging.getLogger('flvlib3.tags').addFilter(f)
        ensure(1, 2, 'error')
        logging.getLogger('flvlib3.tags').removeFilter(f)

        assert f.warnings == 1

    def test_ensure_no_error(self):
        strict_parser(True)
        ensure(1, 1, 'no error')


class BodyGeneratorMixin:
    # this header contains DataSize of 10 and timestamp of 9823
    tag_header = b'\x00\x00\x0a\x00\x26\x5f\x00\x00\x00\x00'
    tag_footer = b'\x00\x00\x00\x15'

    DATA_SIZE = 10

    def tag_body(self, content):
        return self.tag_header + content + b'\x00' * (self.DATA_SIZE - len(content)) + self.tag_footer


class TestTag:

    def test_simple_parse(self):
        s = BytesIO(b'\x00\x00\x0a\x00\x26\x5f\x00\x00\x00\x00' + b'\x11' * 10 + b'\x00\x00\x00\x15')
        t = Tag(None, s)
        t.parse()

        assert s.read() == b''
        # the offset should be BytesIO.tell() - 1, which means -1
        assert t.offset == -1
        assert t.size == BodyGeneratorMixin.DATA_SIZE
        assert t.timestamp == 9823

    def test_negative_timestamp(self):
        s = BytesIO(b'\x00\x00\x0f\xcc\xff\x1b\xff\x00\x00\x00' + b'\x11' * 15 + b'\x00\x00\x00\x1a')
        t = Tag(None, s)

        # This should give a warning
        f = WarningCounterFilter()
        logging.getLogger('flvlib3.tags').addFilter(f)
        t.parse()
        logging.getLogger('flvlib3.tags').removeFilter(f)

        assert f.warnings == 1

        assert s.read() == b''
        assert t.offset == -1
        assert t.size == 15
        assert t.timestamp == -3342565

    def test_zero_size_data(self):
        s = BytesIO(b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x0b')
        t = Tag(None, s)
        t.parse()

        assert s.read() == b''
        assert t.offset == -1
        assert t.size == 0
        assert t.timestamp == 0

    def test_errors(self):
        # nonzero StreamID
        s = BytesIO(b'\x00\x00\x0a\x00\x26\x5f\x00\x00\x00\x01' + b'\x11' * 10 + b'\x00\x00\x00\x15')
        t = Tag(None, s)
        with pytest.raises(MalformedFLV):
            assert t.parse()

        # PreviousTagSize too small
        s = BytesIO(b'\x00\x00\x0a\x00\x26\x5f\x00\x00\x00\x00' + b'\x11' * 10 + b'\x00\x00\x00\x14')
        t = Tag(None, s)
        with pytest.raises(MalformedFLV):
            assert t.parse()

        # PreviousTagSize too big
        s = BytesIO(b'\x00\x00\x0a\x00\x26\x5f\x00\x00\x00\x00' + b'\x11' * 10 + b'\x00\x00\x00\x16')
        t = Tag(None, s)
        with pytest.raises(MalformedFLV):
            assert t.parse()

        # DataSize too big
        s = BytesIO(b'\x00\x00\x10\x00\x26\x5f\x00\x00\x00\x00' + b'\x11' * 10 + b'\x00\x00\x00\x15')
        t = Tag(None, s)
        with pytest.raises(EOFError):
            assert t.parse()

        # file too short
        s = BytesIO(b'\x00\x00\x0a\x00\x26\x5f\x00')
        t = Tag(None, s)
        with pytest.raises(EOFError):
            assert t.parse()


class TestAudioTag(BodyGeneratorMixin):

    def test_simple_sound_flags(self):
        s = BytesIO(self.tag_body(b'\x2d'))
        t = AudioTag(None, s)
        t.parse()

        assert t.offset == -1
        assert t.size == BodyGeneratorMixin.DATA_SIZE
        assert t.timestamp == 9823
        assert t.sound_format == SOUND_FORMAT_MP3
        assert t.sound_rate == SOUND_RATE_44_KHZ
        assert t.sound_size == SOUND_SIZE_8_BIT
        assert t.sound_type == SOUND_TYPE_STEREO

    def test_sound_flags_aac(self):
        s = BytesIO(self.tag_body(b'\xaf\x01'))
        t = AudioTag(None, s)
        t.parse()

        assert t.sound_format == SOUND_FORMAT_AAC
        assert t.sound_rate == SOUND_RATE_44_KHZ
        assert t.sound_size == SOUND_SIZE_16_BIT
        assert t.sound_type == SOUND_TYPE_STEREO
        assert t.aac_packet_type == AAC_PACKET_TYPE_RAW

    def test_errors(self):
        # wrong sound format
        t = AudioTag(None, BytesIO(self.tag_body(b'\x9f')))
        with pytest.raises(MalformedFLV):
            assert t.parse()

        # wrong sound rate for AAC
        t = AudioTag(None, BytesIO(self.tag_body(b'\xa3')))
        with pytest.raises(MalformedFLV):
            assert t.parse()

        # wrong sound type for AAC
        t = AudioTag(None, BytesIO(self.tag_body(b'\xa2')))
        with pytest.raises(MalformedFLV):
            assert t.parse()

        # wrong packet type for AAC
        t = AudioTag(None, BytesIO(self.tag_body(b'\xaf\x03')))
        with pytest.raises(MalformedFLV):
            assert t.parse()

    def test_repr(self):
        t = AudioTag(None, FakeBytesIO(self.tag_body(b'\xbb'), 10))
        assert repr(t) == '<AudioTag unparsed>'

        t.parse()
        assert repr(t) == '<AudioTag at offset 0x00000009, time 9823, size 10, Speex>'

        t = AudioTag(None, FakeBytesIO(self.tag_body(b'\xaf\x01'), 10))
        t.parse()
        assert repr(t) == '<AudioTag at offset 0x00000009, time 9823, size 10, AAC, raw>'


class TestVideoTag(BodyGeneratorMixin):

    def test_simple_video_flags(self):
        s = BytesIO(self.tag_body(b'\x22'))
        t = VideoTag(None, s)
        t.parse()

        assert t.offset == -1
        assert t.size == BodyGeneratorMixin.DATA_SIZE
        assert t.timestamp == 9823
        assert t.frame_type == FRAME_TYPE_INTERFRAME
        assert t.codec_id == CODEC_ID_H263

    def test_video_flags_h264(self):
        s = BytesIO(self.tag_body(b'\x17\x01'))
        t = VideoTag(None, s)
        t.parse()

        assert t.frame_type == FRAME_TYPE_KEYFRAME
        assert t.codec_id == CODEC_ID_H264
        assert t.h264_packet_type == H264_PACKET_TYPE_NALU

    def test_errors(self):
        # wrong frame type
        t = VideoTag(None, BytesIO(self.tag_body(b'\x01')))
        with pytest.raises(MalformedFLV):
            assert t.parse()

        # wrong codec ID
        t = VideoTag(None, BytesIO(self.tag_body(b'\x18')))
        with pytest.raises(MalformedFLV):
            assert t.parse()

        # wrong packet type for H.264
        t = VideoTag(None, BytesIO(self.tag_body(b'\x27\x04')))
        with pytest.raises(MalformedFLV):
            assert t.parse()

    def test_repr(self):
        t = VideoTag(None, FakeBytesIO(self.tag_body(b'\x11'), 10))
        assert repr(t) == '<VideoTag unparsed>'

        t.parse()
        assert repr(t) == '<VideoTag at offset 0x00000009, time 9823, size 10, JPEG (keyframe)>'

        t = VideoTag(None, FakeBytesIO(self.tag_body(b'\x27\x01'), 10))
        t.parse()
        assert repr(t) == '<VideoTag at offset 0x00000009, time 9823, size 10, H.264 (interframe), NAL unit>'


class TestScriptTag:

    def test_simple_script_tag(self):
        s = BytesIO(b'\x00\x00\x07\x00\x26\x5f\x00\x00\x00\x00\x02\x00\x03\x66\x6f\x6f\x05\x00\x00\x00\x12')
        t = ScriptTag(None, s)
        t.parse()

        assert t.offset == -1
        assert t.size == 7
        assert t.timestamp == 9823
        assert t.name == b'foo'
        assert t.variable is None

    def test_variable_parsing(self):
        s = BytesIO(b'\x00\x00\x28\x00\x26\x5f\x00\x00\x00\x00\x02\x00\x0aonMetaData\x08\x00\x00\x00\x01'
                    b'\x00\x08duration\x00\x3f\xf0\x00\x00\x00\x00\x00\x00\x00\x00\x09\x00\x00\x00\x33')
        t = ScriptTag(None, s)
        t.parse()

        assert t.name == b'onMetaData'
        assert t.variable == {b'duration': 1.0}

        # try an ECMAArray without the marker and without strict parsing

        strict_parser(False)
        s = BytesIO(b'\x00\x00\x25\x00\x26\x5f\x00\x00\x00\x00\x02\x00\x0aonMetaData\x08\x00\x00\x00\x01'
                    b'\x00\x08duration\x00\x3f\xf0\x00\x00\x00\x00\x00\x00\x00\x00\x00\x30')
        t = ScriptTag(None, s)
        t.parse()
        strict_parser(True)

        assert t.name == b'onMetaData'
        assert t.variable == {b'duration': 1.0}

    def test_errors(self):
        # name is not a string (no 0x02 byte before the name)
        s = BytesIO(b'\x00\x00\x07\x00\x26\x5f\x00\x00\x00\x00\x03\x00\x03\x66\x6f\x6f\x05\x00\x00\x00\x12')
        t = ScriptTag(None, s)
        with pytest.raises(MalformedFLV):
            assert t.parse()

        # an ECMAArray without the end marker, should fail under strict parsing
        s = BytesIO(b'\x00\x00\x25\x00\x26\x5f\x00\x00\x00\x00\x02\x00\x0aonMetaData\x08\x00\x00\x00\x01'
                    b'\x00\x08duration\x00\x3f\xf0\x00\x00\x00\x00\x00\x00\x00\x00\x00\x30')
        t = ScriptTag(None, s)
        with pytest.raises(EOFError):
            assert t.parse()

    def test_repr(self):
        s = FakeBytesIO(b'\x00\x00\x07\x00\x26\x5f\x00\x00\x00\x00\x02\x00\x03\x66\x6f\x6f\x05\x00\x00\x00\x12',
                        10)
        t = ScriptTag(None, s)
        assert repr(t) == '<ScriptTag unparsed>'

        t.parse()
        assert repr(t) == "<ScriptTag b'foo' at offset 0x00000009, time 9823, size 7>"


class TestScriptAMF3Tag:

    def test_simple_script_amf3_tag(self):
        s = BytesIO(b'\x00\x00\x17\x00\x00\x4d\x00\x00\x00\x00\x00\x02\x00\x0a\x73\x74\x72\x65\x61\x6d'
                    b'\x50\x69\x6e\x67\x00\x42\x74\x29\xa6\xff\x4b\x50\x00\x00\x00\x00\x22')
        t = ScriptAMF3Tag(None, s)
        t.parse()

        assert t.offset == -1
        assert t.size == 23
        assert t.timestamp == 77

    def test_repr(self):
        s = FakeBytesIO(b'\x00\x00\x17\x00\x00\x4d\x00\x00\x00\x00\x00\x02\x00\x0a\x73\x74\x72\x65\x61\x6d'
                        b'\x50\x69\x6e\x67\x00\x42\x74\x29\xa6\xff\x4b\x50\x00\x00\x00\x00\x22',
                        10)
        t = ScriptAMF3Tag(None, s)
        assert repr(t) == '<ScriptAMF3Tag unparsed>'

        t.parse()
        assert repr(t) == '<ScriptAMF3Tag at offset 0x00000009, time 77, size 23>'


class TestFLV(BodyGeneratorMixin):

    def test_simple_parse(self):
        s = BytesIO(b'FLV\x00\x04\x00\x00\x00\x09\x00\x00\x00\x00')
        f = FLV(s)
        f.parse_header()

        assert f.version == 0
        assert f.has_audio
        assert not f.has_video

    def test_parse_tags(self):
        s = BytesIO(b'FLV\x00\x05\x00\x00\x00\x09\x00\x00\x00\x00'
                    b'\x08' + self.tag_body(b'\x4b') +
                    b'\x08' + self.tag_body(b'\xbb') +
                    b'\x09' + self.tag_body(b'\x17\x00') +
                    b'\x0f' + (b'\x00\x00\x17\x00\x00\x4d\x00\x00\x00\x00'
                               b'\x00\x02\x00\x0a\x73\x74\x72\x65\x61\x6d'
                               b'\x50\x69\x6e\x67\x00\x42\x74\x29\xa6\xff'
                               b'\x4b\x50\x00\x00\x00\x00\x22') +
                    b'\x12' + (b'\x00\x00\x07\x00\x26\x5f\x00\x00\x00\x00'
                               b'\x02\x00\x03\x66\x6f\x6f\x05\x00\x00\x00\x12'))
        f = FLV(s)
        f.read_tags()

        assert f.version == 0
        assert f.has_audio
        assert f.has_video

        assert len(f.tags) == 5
        assert isinstance(f.tags[0], AudioTag)
        assert isinstance(f.tags[1], AudioTag)
        assert isinstance(f.tags[2], VideoTag)
        assert isinstance(f.tags[3], ScriptAMF3Tag)
        assert isinstance(f.tags[4], ScriptTag)

    def test_errors(self):
        # file shorter than 3 bytes
        s = BytesIO()
        f = FLV(s)
        with pytest.raises(MalformedFLV):
            assert f.read_tags()

        # header invalid
        s = BytesIO(b'XLV\x00\x04\x00\x00\x00\x09\x00\x00\x00\x00')
        f = FLV(s)
        with pytest.raises(MalformedFLV):
            assert f.read_tags()

        # invalid tag type
        s = BytesIO(b'FLV\x00\x05\x00\x00\x00\x09\x00\x00\x00\x00'
                    b'\x01' + self.tag_body(b'\x4b'))
        f = FLV(s)
        with pytest.raises(MalformedFLV):
            assert f.read_tags()


class TestCreateTags:

    def test_create_flv_tag(self):
        s = create_flv_tag(0x08, b'random-garbage', 1234)
        assert s == b'\x08\x00\x00\x0e\x00\x04\xd2\x00\x00\x00\x00random-garbage\x00\x00\x00\x19'

    def test_create_script_tag(self):
        s = create_script_tag(b'onMetaData', {'silly': True})

        assert s == (b'\x12\x00\x00\x1e\x00\x00\x00\x00\x00\x00\x00\x02\x00\x0aonMetaData\x08\x00\x00'
                     b'\x00\x01\x00\x05silly\x01\x01\x00\x00\x09\x00\x00\x00\x29')

    def test_create_flv_header(self):
        data = (
            ((True, True), b'FLV\x01\x05\x00\x00\x00\t\x00\x00\x00\x00'),
            ((True, False), b'FLV\x01\x04\x00\x00\x00\t\x00\x00\x00\x00'),
            ((False, True), b'FLV\x01\x01\x00\x00\x00\t\x00\x00\x00\x00'),
            ((False, False), b'FLV\x01\x00\x00\x00\x00\t\x00\x00\x00\x00')
        )
        for has_audio_video, expected in data:
            s = create_flv_header(*has_audio_video)
            assert s == expected
