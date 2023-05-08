import logging

__version__ = '0.2.1'

logger = logging.getLogger('flvlib3')
handler = logging.StreamHandler()
formatter = logging.Formatter("%(levelname)-7s %(name)-20s %(message)s (%(pathname)s:%(lineno)d)")
handler.setFormatter(formatter)
logger.addHandler(handler)
