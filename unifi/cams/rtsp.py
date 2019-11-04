import logging
import os
import subprocess
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
            default="-vcodec copy -acodec copy",
            help="Transcoding args for `ffmpeg -i <src> <args> <dst>`",
        )

    def __init__(self, args, logger=None):
        self.logger = logger
        self.args = args
        self.dir = tempfile.mkdtemp()
        self.logger.info(self.dir)
        cmd = 'ffmpeg -y -re -i "{}" -vf fps=1 -update 1 {}/screen.jpg'.format(
            self.args.source, self.dir
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
        cmd = 'ffmpeg -y -re -i "{}" {} -metadata streamname={} -f flv - | {} -m unifi.clock_sync | nc {} 6666'.format(
            self.args.source, self.args.ffmpeg_args, stream_name, self.args.host
        )
        self.logger.info("Spwaning ffmpeg (%s): %s", stream_name, cmd)
        if (
            stream_name not in self.streams
            or self.streams[stream_name].poll() is not None
        ):
            self.streams[stream_name] = subprocess.Popen(
                cmd, stdout=FNULL, stderr=subprocess.STDOUT, shell=True
            )
