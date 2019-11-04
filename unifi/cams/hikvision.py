import logging
import os
import subprocess
import sys
import shutil

import tempfile
import requests
from requests.auth import HTTPDigestAuth

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

    def get_snapshot(self):
        img_file = "{}/screen.jpg".format(self.dir)
        uri = "http://{}/ISAPI/Streaming/channels/101/picture?videoResolutionWidth=1280&videoResolutionHeight=720".format(
            self.args.ip
        )
        resp = requests.get(
            uri,
            auth=HTTPDigestAuth(self.args.username, self.args.password),
            stream=True,
        )
        resp.raw.decode_content = True
        shutil.copyfileobj(resp.raw, open(img_file, "wb"))
        return img_file

    def change_video_settings(self, options):
        tilt = int((900 * int(options["brightness"])) / 100)
        pan = int((3600 * int(options["contrast"])) / 100)
        zoom = int((40 * int(options["hue"])) / 100)
        req = """<PTZData>
<AbsoluteHigh>
<elevation> {} </elevation>
<azimuth> {} </azimuth>
<absoluteZoom> {} </absoluteZoom>
</AbsoluteHigh>
</PTZData>
        """.format(
            tilt, pan, zoom
        )
        uri = "http://{}/ISAPI/PTZCtrl/channels/1/absolute".format(self.args.ip)
        requests.put(
            uri, auth=HTTPDigestAuth(self.args.username, self.args.password), data=req
        )
        self.logger.info("Moving to %s:%s:%s", pan, tilt, zoom)
        pass

    def change_video_settings(self, options):
        tilt = int((900 * int(options["brightness"])) / 100)
        pan = int((3600 * int(options["contrast"])) / 100)
        zoom = int((40 * int(options["hue"])) / 100)
        req = """<PTZData>
<AbsoluteHigh>
<elevation> {} </elevation>
<azimuth> {} </azimuth>
<absoluteZoom> {} </absoluteZoom>
</AbsoluteHigh>
</PTZData>
        """.format(
            tilt, pan, zoom
        )
        uri = "http://{}/ISAPI/PTZCtrl/channels/1/absolute".format(self.args.ip)
        requests.put(
            uri, auth=HTTPDigestAuth(self.args.username, self.args.password), data=req
        )
        self.logger.info("Moving to %s:%s:%s", pan, tilt, zoom)
        pass

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
