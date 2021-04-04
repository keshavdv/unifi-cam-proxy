import argparse
import asyncio
import logging
import os

import coloredlogs

from unifi.cams.hikvision import HikvisionCam
from unifi.cams.rtsp import RTSPCam
from unifi.core import Core

CAMS = {"hikvision": HikvisionCam, "rtsp": RTSPCam}

logging.basicConfig()
coloredlogs.install(level="DEBUG")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", "-H", required=True, help="NVR ip address and port")
    parser.add_argument(
        "--cert",
        "-c",
        required=True,
        default="client.pem",
        help="Client certificate path",
    )
    parser.add_argument("--token", "-t", default="", help="Adoption token")
    parser.add_argument("--mac", "-m", default="44D9E7407670", help="MAC address")
    parser.add_argument(
        "--ip", "-i", default="192.168.1.10", help="IP address of camera"
    )
    parser.add_argument(
        "--name", "-n", default="unifi-cam-proxy", help="Name of camera"
    )
    parser.add_argument(
        "--protect",
        "-p",
        default=False,
        action="store_true",
        help="Set if connecting to Unifi Protect",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="increase output verbosity"
    )

    sp = parser.add_subparsers(help="Camera implementations", dest="impl")
    for (name, impl) in CAMS.items():
        subparser = sp.add_parser(name)
        impl.add_parser(subparser)
    return parser.parse_args()


def main():
    args = parse_args()
    klass = CAMS[args.impl]

    core_logger = logging.getLogger("Core")
    logger = logging.getLogger(klass.__name__)
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        core_logger.setLevel(logging.DEBUG)

    cam = klass(args, logger)
    c = Core(args, cam, core_logger)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(c.run())


if __name__ == "__main__":
    main()
