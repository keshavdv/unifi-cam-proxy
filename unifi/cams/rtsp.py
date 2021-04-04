import logging
import os
import subprocess
import sys
import tempfile

from unifi.cams.base import UnifiCamBase

FNULL = open(os.devnull, "w")


class RTSPCam(UnifiCamBase):
    @classmethod
    def add_parser(self, parser):
        parser.add_argument("--source", "-s", required=True, help="Stream source")
        parser.add_argument(
            "--ffmpeg-args",
            "-f",
            default="-vcodec copy -strict -2 -c:a aac",
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
        cmd = 'ffmpeg -y -re -rtsp_transport {} -i "{}" -vf fps=1 -update 1 {}/screen.jpg'.format(
            self.args.rtsp_transport,
            self.args.source,
            self.dir,
        )
        self.logger.info(cmd)
        self.streams = {
            "mjpg": subprocess.Popen(
                cmd, stdout=FNULL, stderr=subprocess.STDOUT, shell=True
            )
        }

    def get_snapshot(self):
        return "{}/screen.jpg".format(self.dir)

    def start_video_stream(self, stream_name, options):
        cmd = 'ffmpeg -y -f lavfi -i aevalsrc=0 -rtsp_transport {} -i "{}" {} -metadata streamname={} -f flv - | {} -m unifi.clock_sync | nc {} {}'.format(
            self.args.rtsp_transport,
            self.args.source,
            self.args.ffmpeg_args,
            stream_name,
            sys.executable,
            self.args.host,
            7550 if self.args.protect else 6666,
        )
        self.logger.info("Spawning ffmpeg (%s): %s", stream_name, cmd)
        if (
            stream_name not in self.streams
            or self.streams[stream_name].poll() is not None
        ):
            self.streams[stream_name] = subprocess.Popen(
                cmd, stdout=FNULL, stderr=subprocess.STDOUT, shell=True
            )
