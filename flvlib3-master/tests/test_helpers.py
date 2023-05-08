import datetime

from flvlib3.helpers import *


class TestUTCTimezone:

    utc = UTC()
    now = datetime.datetime.now()

    def test_utcoffset(self):
        assert self.utc.utcoffset(self.now) == datetime.timedelta(0)

    def test_tzname(self):
        assert self.utc.tzname(self.now) == 'UTC'

    def test_dst(self):
        assert self.utc.dst(self.now) == datetime.timedelta(0)
