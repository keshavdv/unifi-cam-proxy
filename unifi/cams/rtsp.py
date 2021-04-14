import logging
import os
import subprocess
import sys
import tempfile
from typing import Tuple

from unifi.cams.base import UnifiCamBase

FNULL = open(os.devnull, "w")


class RTSPCam(UnifiCamBase):
    @classmethod
    def add_parser(self, parser):
        parser.add_argument("--source", "-s", required=True, help="Stream source")
        parser.add_argument(
            "--ffmpeg-args",
            "-f",
            default="-f lavfi -i aevalsrc=0  -vcodec copy -strict -2 -c:a aac",
            help="Transcoding args for `ffmpeg -i <src> <args> <dst>`",
        )
        parser.add_argument(
            "--rtsp-transport",
            default="tcp",
            choices=["tcp", "udp", "http", "udp_multicast"],
            help="RTSP transport protocol used by stream",
        )

    def __init__(self, args, logger=None):
        self.logger = logger
        self.args = args
        self.dir = tempfile.mkdtemp()
        self.logger.info(self.dir)
        cmd = f'ffmpeg -y -re -rtsp_transport {self.args.rtsp_transport} -i "{self.args.source}" -vf fps=1 -update 1 {self.dir}/screen.jpg'
        self.logger.info(cmd)
        self.streams = {
            "mjpg": subprocess.Popen(
                cmd, stdout=FNULL, stderr=subprocess.STDOUT, shell=True
            )
        }

    def get_snapshot(self):
        return "{}/screen.jpg".format(self.dir)

    def start_video_stream(
        self, stream_index: str, stream_name: str, destination: Tuple[str, int]
    ):
        cmd = f'ffmpeg -y -rtsp_transport {self.args.rtsp_transport} -i "{self.args.source}" {self.args.ffmpeg_args} -metadata streamname={stream_name} -f flv - | {sys.executable} -m unifi.clock_sync | nc {destination[0]} {destination[1]}'
        self.logger.info("Spawning ffmpeg (%s): %s", stream_name, cmd)
        if (
            stream_name not in self.streams
            or self.streams[stream_name].poll() is not None
        ):
            self.streams[stream_name] = subprocess.Popen(
                cmd, stdout=FNULL, stderr=subprocess.STDOUT, shell=True
            )
