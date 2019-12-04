import logging
import os
import subprocess
import sys
import shutil

import tempfile
import requests
import xmltodict
from requests.auth import HTTPDigestAuth
from hikvisionapi import Client

from unifi.cams.base import UnifiCamBase

FNULL = open(os.devnull, "w")


class HikvisionCam(UnifiCamBase):
    @classmethod
    def add_parser(self, parser):
        parser.add_argument("--username", "-u", required=True, help="Camera username")
        parser.add_argument("--password", "-p", required=True, help="Camera password")

    def __init__(self, args, logger=None):
        self.logger = logger
        self.args = args
        self.dir = tempfile.mkdtemp()
        self.streams = {}
        self.cam = Client(
            "http://{}".format(self.args.ip), self.args.username, self.args.password
        )

    def get_snapshot(self):
        img_file = "{}/screen.jpg".format(self.dir)
        resp = self.cam.Streaming.channels[102].picture(
            method="get", type="opaque_data"
        )
        with open(img_file, "wb") as f:
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
        return self.get_video_settings()

    def start_video_stream(self, stream_name, video_mode):
        channel = 1
        if video_mode == "video3":
            channel = 2

        vid_src = "rtsp://{}:{}@{}:554/Streaming/Channels/{}/".format(
            self.args.username, self.args.password, self.args.ip, channel
        )

        cmd = 'ffmpeg -y -f lavfi -i aevalsrc=0 -i "{}" -vcodec copy -use_wallclock_as_timestamps 1 -strict -2 -c:a aac -metadata streamname={} -f flv - | {} -m unifi.clock_sync | nc {} 6666'.format(
            vid_src, stream_name, sys.executable, self.args.host
        )
        self.logger.info("Spawning ffmpeg: %s", cmd)
        if (
            stream_name not in self.streams
            or self.streams[stream_name].poll() is not None
        ):
            self.streams[stream_name] = subprocess.Popen(
                cmd, stdout=FNULL, stderr=subprocess.STDOUT, shell=True
            )
