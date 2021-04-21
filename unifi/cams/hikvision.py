import tempfile
from pathlib import Path

import xmltodict
from hikvisionapi import Client

from unifi.cams.base import UnifiCamBase


class HikvisionCam(UnifiCamBase):
    def __init__(self, args, logger=None):
        super().__init__(args, logger)
        self.snapshot_dir = tempfile.mkdtemp()
        self.streams = {}
        self.cam = Client(
            f"http://{self.args.ip}", self.args.username, self.args.password
        )

    @classmethod
    def add_parser(self, parser):
        super().add_parser(parser)
        parser.add_argument("--username", "-u", required=True, help="Camera username")
        parser.add_argument("--password", "-p", required=True, help="Camera password")

    async def get_snapshot(self):
        img_file = Path(self.snapshot_dir, "screen.jpg")

        resp = self.cam.Streaming.channels[102].picture(
            method="get", type="opaque_data"
        )
        with img_file.open("wb") as f:
            for chunk in resp.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)
        return img_file

    def get_video_settings(self):
        r = self.cam.PTZCtrl.channels[1].status(method="get")["PTZStatus"][
            "AbsoluteHigh"
        ]
        return {
            # Tilt/elevation
            "brightness": int(100 * int(r["azimuth"]) / 3600),
            # Pan/azimuth
            "contrast": int(100 * int(r["azimuth"]) / 3600),
            # Zoom
            "hue": int(100 * int(r["absoluteZoom"]) / 40),
        }

    def change_video_settings(self, options):
        tilt = int((900 * int(options["brightness"])) / 100)
        pan = int((3600 * int(options["contrast"])) / 100)
        zoom = int((40 * int(options["hue"])) / 100)

        self.logger.info("Moving to %s:%s:%s", pan, tilt, zoom)
        req = {
            "PTZData": {
                "@version": "2.0",
                "@xmlns": "http://www.hikvision.com/ver20/XMLSchema",
                "AbsoluteHigh": {
                    "absoluteZoom": str(zoom),
                    "azimuth": str(pan),
                    "elevation": str(tilt),
                },
            }
        }
        self.cam.PTZCtrl.channels[1].absolute(
            method="put", data=xmltodict.unparse(req, pretty=True)
        )

    def get_stream_source(self, stream_index: str):
        channel = 1
        if stream_index != "video1":
            channel = 3

        return f"rtsp://{self.args.username}:{self.args.password}@{self.args.ip}:554/Streaming/Channels/{channel}/"
