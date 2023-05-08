import os
import datetime

__all__ = ['UTC', 'utc', 'force_remove']


class UTC(datetime.tzinfo):
    """
    A UTC tzinfo class, based on
    http://docs.python.org/library/datetime.html#datetime.tzinfo
    """

    ZERO = datetime.timedelta(0)

    def utcoffset(self, dt):
        return self.ZERO

    def tzname(self, dt):
        return "UTC"

    def dst(self, dt):
        return self.ZERO


utc = UTC()


def force_remove(path):
    try:
        os.remove(path)
    except OSError:
        pass
