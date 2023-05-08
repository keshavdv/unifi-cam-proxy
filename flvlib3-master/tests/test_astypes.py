from io import BytesIO
from datetime import datetime, timedelta, tzinfo

import pytest

from flvlib3.astypes import *
from flvlib3.constants import *
from flvlib3.primitives import *


class FakeTZInfo(tzinfo):

    def __init__(self, m):
        self.m = m

    def utcoffset(self, dt):
        return timedelta(minutes=self.m)

    def dst(self, dt):
        return timedelta(0)

    def tzname(self, dt):
        return 'Fake Timezone'


class TestASTypes:

    def test_number(self):
        assert get_number(BytesIO(b'\x40\x97\xfa\x9d\xb2\x2d\x0e\x56')) == 1534.654
        assert make_number(-4.32) == b'\xc0\x11\x47\xae\x14\x7a\xe1\x48'

    def test_boolean(self):
        assert get_boolean(BytesIO(b'\x05'))
        assert not get_boolean(BytesIO(b'\x00'))
        assert make_boolean(False) == b'\x00'

    def test_string(self):
        assert get_string(BytesIO(b'\x00\x0btest string')) == b'test string'
        assert get_string(
            BytesIO(b'\x00\x0f\xe4\xbd\xa0\xe5\xa5\xbd\xef\xbc\x8c\xe4\xb8\x96\xe7\x95\x8c')
        ) == b'\xe4\xbd\xa0\xe5\xa5\xbd\xef\xbc\x8c\xe4\xb8\x96\xe7\x95\x8c'
        assert make_string(
            b'\xe4\xbd\xa0\xe5\xa5\xbd\xef\xbc\x8c\xe4\xb8\x96\xe7\x95\x8c'
        ) == b'\x00\x0f\xe4\xbd\xa0\xe5\xa5\xbd\xef\xbc\x8c\xe4\xb8\x96\xe7\x95\x8c'
        assert make_string(b'\xce\xbb') == b'\x00\x02\xce\xbb'
        # A random blob should also work
        assert make_string(
            b'\x45\x2d\x6e\x55\x00\x23\x50'
        ) == b'\x00\x07\x45\x2d\x6e\x55\x00\x23\x50'

    def test_long_string(self):
        assert get_long_string(BytesIO(b'\x00\x00\x00\x0btest string')) == b'test string'
        assert get_long_string(
            BytesIO(b'\x00\x00\x00\x0f\xe4\xbd\xa0\xe5\xa5\xbd\xef\xbc\x8c\xe4\xb8\x96\xe7\x95\x8c')
        ) == b'\xe4\xbd\xa0\xe5\xa5\xbd\xef\xbc\x8c\xe4\xb8\x96\xe7\x95\x8c'
        assert make_long_string(
            b'\xe4\xbd\xa0\xe5\xa5\xbd\xef\xbc\x8c\xe4\xb8\x96\xe7\x95\x8c'
        ) == b'\x00\x00\x00\x0f\xe4\xbd\xa0\xe5\xa5\xbd\xef\xbc\x8c\xe4\xb8\x96\xe7\x95\x8c'
        assert make_long_string(b'\xce\xbb') == b'\x00\x00\x00\x02\xce\xbb'
        # A random blob should also work
        assert make_long_string(
            b'\x45\x2d\x6e\x55\x00\x23\x50'
        ) == b'\x00\x00\x00\x07\x45\x2d\x6e\x55\x00\x23\x50'
        assert make_long_string(b'') == b'\x00\x00\x00\x00'

        # Long strings are not getter/maker equivalent, because *all*
        # strings are serialized as normal strings, not long strings.
        # So to Test proper deserialization from script_data_values we
        # need to do it manually.
        val = b'a test long string'
        # serialize, should get a string
        assert make_script_data_value(val) == make_ui8(VALUE_TYPE_STRING) + b'\x00\x12a test long string'
        # deserialize a long string
        s = BytesIO(make_ui8(VALUE_TYPE_LONG_STRING) + make_long_string(val))
        assert val == get_script_data_value(s)
        assert s.read() == b''

    def test_ecma_array(self):
        assert get_ecma_array(
            BytesIO(b'\x00\x00\x00\x01\x00\x08test key\x00\x3f\xf0\x00\x00\x00\x00\x00\x00\x00\x00\x09')
        ) == {b'test key': 1}

        # try a wrong approximate array size, should be parsed anyway
        assert get_ecma_array(
            BytesIO(
                b'\x00\x00\x00\x04\x00\x00\x01\x00\x00\x01 \x00\x40\x08\x00\x00\x00\x00\x00\x00'
                b'\x00\x03goo\x02\x00\x02\xce\xbb\x00\x00\x09'
            )
        ) == {b'': False, b' ': 3, b'goo': b'\xce\xbb'}
        assert make_ecma_array({'key': 'val'}) == b'\x00\x00\x00\x01\x00\x03key\x02\x00\x03val\x00\x00\x09'

        d = ECMAArray()
        for key, val in (('key', 7.4), ('w00t', 'w00t'), ('Flower!', 'λ')):
            d[key] = val
        assert make_ecma_array(d) == b'\x00\x00\x00\x03\x00\x03key\x00\x40\x1d\x99\x99\x99\x99\x99\x9a\x00' \
                                     b'\x04w00t\x02\x00\x04w00t\x00\x07Flower!\x02\x00\x02\xce\xbb\x00\x00\x09'

        # Various corner cases:

        # try using the max_offset kwarg and removing the marker
        assert get_ecma_array(
            BytesIO(
                b'\x00\x00\x00\x04\x00\x00\x01\x00\x00\x01 \x00\x40\x08\x00\x00\x00\x00\x00\x00'
                b'\x00\x03goo\x02\x00\x02\xce\xbb\x00\x00'
            ),
            max_offset=30
        ) == {b'': False, b' ': 3, b'goo': b'\xce\xbb'}
        # try not using the max_offset kwarg and removing the marker, should fail
        with pytest.raises(EOFError):
            assert get_ecma_array(
                BytesIO(
                    b'\x00\x00\x00\x04\x00\x00\x01\x00\x00\x01 \x00\x40\x08\x00\x00\x00\x00\x00\x00'
                    b'\x00\x03goo\x02\x00\x02\xce\xbb\x00\x00'
                )
            )

    def test_strict_array(self):
        assert get_strict_array(BytesIO(b'\x00\x00\x00\x01\x00\x3f\xf0\x00\x00\x00\x00\x00\x00')) == [1]

        assert get_strict_array(
            BytesIO(
                b'\x00\x00\x00\x06\x00\x40\x08\x00\x00\x00\x00\x00\x00\x01\x00\x02\x00\x00\x00\xc0\x15\x99\x99\x99'
                b'\x99\x99\x9a\x02\x00\x02\xce\xbb\x01\x01'
            )
        ) == [3, False, b'', -5.4, b'\xce\xbb', True]

        assert make_strict_array(
            [-1, 'foo']
        ) == b'\x00\x00\x00\x02\x00\xbf\xf0\x00\x00\x00\x00\x00\x00\x02\x00\x03\x66\x6f\x6f'

        # Various corner cases:

        # try wrong array size, should fail
        with pytest.raises(EOFError):
            assert get_strict_array(
                BytesIO(
                    b'\x00\x00\x00\x07\x00\x40\x08\x00\x00\x00\x00\x00\x00\x01\x00\x02\x00\x00\x00\xc0'
                    b'\x15\x99\x99\x99\x99\x99\x9a\x02\x00\x02\xc2\xbb\x01\x01'
                )
            )

    def test_date(self):
        date = b'\x42\x5d\x2b\x75\x29\xaa\x00\x00'
        expected = datetime(1985, 11, 18, 3, 30, 1, tzinfo=FakeTZInfo(0))
        assert get_date(BytesIO(date + b'\x00\x00')) == expected
        # the time offset gets ignored
        assert get_date(BytesIO(date + b'\x00\x1e')) == expected
        assert get_date(
            BytesIO(b'\x42\x5d\x2b\x7c\x07\x7a\x00\x00\x00\x00')
        ) == datetime(1985, 11, 18, 4, 0, 1, tzinfo=FakeTZInfo(0))
        # timezone-aware datetimes are converted to UTC and no time offset is stored
        assert make_date(
            datetime(2009, 1, 1, 20, 0, 0, tzinfo=FakeTZInfo(10))
        ) == b'\x42\x71\xe9\x3b\xec\x64\x00\x00\x00\x00'
        # naive datetimes are assumed to be in UTC
        assert make_date(datetime(2009, 1, 1, 19, 50, 0, )) == b'\x42\x71\xe9\x3b\xec\x64\x00\x00\x00\x00'

    def test_null(self):
        assert get_null(BytesIO(b'')) is None
        assert make_null(BytesIO(b'')) == b''

    def test_object(self):
        # these tests are almost identical to ECMA array's
        o = FLVObject({b'test key': 1})
        assert get_object(BytesIO(b'\x00\x08test key\x00\x3f\xf0\x00\x00\x00\x00\x00\x00\x00\x00\x09')) == o
        assert make_object({b'key': b'val'}) == b'\x00\x03key\x02\x00\x03val\x00\x00\x09'

        o = FLVObject({
            k: v for k, v in ((b'key', 7.4), ('w00t', b'w00t'), ('Flower!', 'λ'))
        })
        assert make_object(o) == b'\x00\x03key\x00\x40\x1d\x99\x99\x99\x99\x99\x9a\x00\x04w00t\x02\x00\x04' \
                                 b'w00t\x00\x07Flower!\x02\x00\x02\xce\xbb\x00\x00\x09'

        class Dummy:
            pass

        d = Dummy()
        d.x = 1
        assert make_object(d) == b'\x00\x01\x78\x00\x3f\xf0\x00\x00\x00\x00\x00\x00\x00\x00\x09'

        # Various corner cases:

        # try using the max_offset kwarg and removing the marker
        o = FLVObject({
            k: v for k, v in ((b'', False), (b' ', 3), (b'goo', b'\xce\xbb'))
        })
        assert get_object(
            BytesIO(
                b'\x00\x00\x01\x00\x00\x01 \x00\x40\x08\x00\x00\x00\x00\x00\x00\x00\x03goo\x02\x00\x02'
                b'\xce\xbb\x00\x00'
            ),
            max_offset=26
        ) == o
        # try not using the max_offset kwarg and removing the marker, should fail
        with pytest.raises(EOFError):
            assert get_object(
                BytesIO(
                    b'\x00\x00\x01\x00\x00\x01 \x00\x40\x08\x00\x00\x00\x00\x00\x00\x00\x03goo\x02\x00\x02'
                    b'\xce\xbb\x00\x00'
                )
            )

    def test_movie_clip(self):
        assert get_movie_clip(BytesIO(b'\x00\x0d/path/to/clip')) == MovieClip(b'/path/to/clip')
        assert make_movie_clip(MovieClip(b'/other/path')) == b'\x00\x0b/other/path'

        # Test human-readable representation
        assert repr(MovieClip('path')) == '<MovieClip at path>'

    def test_undefined(self):
        assert get_undefined(BytesIO(b'')) == Undefined()
        assert make_undefined(Undefined()) == b''

        # Test human-readable representation
        assert repr(Undefined()) == '<Undefined>'

    def test_reference(self):
        assert get_reference(BytesIO(b'\x01\x56')) == Reference(342)
        assert make_reference(Reference(0)) == b'\x00\x00'

        # Test human-readable representation
        assert repr(Reference(1)) == '<Reference to 1>'

    def test_script_data_value(self):
        assert get_script_data_value(
            BytesIO(
                b'\x08\x00\x00\x00\x01\x00\x03\x66\x6f\x6f\x0a\x00\x00\x00\x03\x01\x00\x05\x0a\x00\x00'
                b'\x00\x01\x00\x40\x0c\x00\x00\x00\x00\x00\x00\x00\x00\x09'
            )
        ) == {b'foo': [False, None, [3.5]]}

        assert make_script_data_value(
            ['string', 0]
        ) == b'\x0a\x00\x00\x00\x02\x02\x00\x06\x73\x74\x72\x69\x6e\x67\x00\x00\x00\x00\x00\x00\x00\x00\x00'

        # Various corner cases:

        # Invalid value type
        with pytest.raises(MalformedFLV):
            assert get_script_data_value(
                BytesIO(
                    b'\x09\x00\x00\x00\x01\x00\x03\x66\x6f\x6f\x0a\x00\x00\x00\x03\x01\x00\x05\x0a\x00\x00'
                    b'\x00\x01\x00\x40\x0c\x00\x00\x00\x00\x00\x00\x00\x00\x09'
                )
            )

    def test_script_data_variable(self):
        assert get_script_data_variable(BytesIO(b'\x00\x03\x66\x6f\x6f\x05')) == (b'foo', None)

        # can't just add a maker Test, because it expects the maker to accept only one argument
        assert make_script_data_variable(
            'variable name', [1, 2, b'3']
        ) == b'\x00\x0d\x76\x61\x72\x69\x61\x62\x6c\x65\x20\x6e\x61\x6d\x65\x0a\x00' \
             b'\x00\x00\x03\x00\x3f\xf0\x00\x00\x00\x00\x00\x00\x00\x40\x00\x00\x00' \
             b'\x00\x00\x00\x00\x02\x00\x01\x33'
