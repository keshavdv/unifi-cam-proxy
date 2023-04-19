import argparse
import asyncio
import logging
import sys
from shutil import which

import coloredlogs
from pyunifiprotect import ProtectApiClient

from unifi.cams import (
    DahuaCam,
    FrigateCam,
    HikvisionCam,
    Reolink,
    ReolinkNVRCam,
    RTSPCam,
)
from unifi.core import Core
from unifi.version import __version__

CAMS = {
    "amcrest": DahuaCam,
    "dahua": DahuaCam,
    "frigate": FrigateCam,
    "hikvision": HikvisionCam,
    "lorex": DahuaCam,
    "reolink": Reolink,
    "reolink_nvr": ReolinkNVRCam,
    "rtsp": RTSPCam,
}


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--host", "-H", required=True, help="NVR ip address and port")
    parser.add_argument("--nvr-username", required=False, help="NVR username")
    parser.add_argument("--nvr-password", required=False, help="NVR password")
    parser.add_argument(
        "--cert",
        "-c",
        required=True,
        default="client.pem",
        help="Client certificate path",
    )
    parser.add_argument(
        "--token", "-t", required=False, default=None, help="Adoption token"
    )
    parser.add_argument("--mac", "-m", default="AABBCCDDEEFF", help="MAC address")
    parser.add_argument(
        "--ip",
        "-i",
        default="192.168.1.10",
        help="IP address of camera (only used to display in UI)",
    )
    parser.add_argument(
        "--name",
        "-n",
        default="unifi-cam-proxy",
        help="Name of camera (only works for UFV)",
    )
    parser.add_argument(
        "--model",
        default="UVC G3",
        choices=[
            "UVC",
            "UVC AI 360",
            "UVC AI Bullet",
            "UVC AI THETA",
            "UVC AI DSLR",
            "UVC Pro",
            "UVC Dome",
            "UVC Micro",
            "UVC G3",
            "UVC G3 Battery",
            "UVC G3 Dome",
            "UVC G3 Micro",
            "UVC G3 Mini",
            "UVC G3 Instant",
            "UVC G3 Pro",
            "UVC G3 Flex",
            "UVC G4 Bullet",
            "UVC G4 Pro",
            "UVC G4 PTZ",
            "UVC G4 Doorbell",
            "UVC G4 Doorbell Pro",
            "UVC G4 Doorbell Pro PoE",
            "UVC G4 Dome",
            "UVC G4 Instant",
            "UVC G5 Bullet",
            "UVC G5 Dome",
            "UVC G5 Flex",
            "UVC G5 Pro",
            "AFi VC",
            "Vision Pro",
        ],
        help="Hardware model to identify as",
    )
    parser.add_argument(
        "--fw-version",
        "-f",
        default="UVC.S2L.v4.23.8.67.0eba6e3.200526.1046",
        help="Firmware version to initiate connection with",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="increase output verbosity"
    )

    sp = parser.add_subparsers(
        help="Camera implementations",
        dest="impl",
        required=True,
    )
    for name, impl in CAMS.items():
        subparser = sp.add_parser(name)
        impl.add_parser(subparser)
    return parser.parse_args()


async def generate_token(args, logger):
    try:
        protect = ProtectApiClient(
            args.host, 443, args.nvr_username, args.nvr_password, verify_ssl=False
        )
        await protect.update()
        response = await protect.api_request("cameras/manage-payload")
        return response["mgmt"]["token"]
    except Exception:
        logger.exception(
            "Could not automatically fetch token, please see docs at"
            " https://unifi-cam-proxy.com/"
        )
        return None
    finally:
        await protect.close_session()


async def run():
    args = parse_args()
    klass = CAMS[args.impl]

    core_logger = logging.getLogger("Core")
    class_logger = logging.getLogger(klass.__name__)

    level = logging.INFO
    if args.verbose:
        level = logging.DEBUG

    for logger in [core_logger, class_logger]:
        coloredlogs.install(level=level, logger=logger)

    # Preflight checks
    for binary in ["ffmpeg", "nc"]:
        if which(binary) is None:
            logger.error(f"{binary} is not installed")
            sys.exit(1)

    if not args.token:
        args.token = await generate_token(args, logger)

    if not args.token:
        logger.error("A valid token is required")
        sys.exit(1)

    cam = klass(args, logger)
    c = Core(args, cam, core_logger)
    await c.run()


def main():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run())


if __name__ == "__main__":
    main()
