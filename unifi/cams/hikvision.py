import logging
import os
import subprocess
import tempfile
import requests
from requests.auth import HTTPDigestAuth

FNULL = open(os.devnull, 'w')

class HikvisionCam(object):

    @classmethod
    def add_parser(self, parser):
        parser.add_argument('--username', '-u', required=True, help='Camera username')
        parser.add_argument('--password', '-p', required=True, help='Camera password')
        parser.add_argument('--source', '-s', required=True, help='Camera ip')

    def __init__(self, args, logger=None):
        self.logger = logger
        self.args = args
        self.dir = tempfile.mkdtemp()
        self.logger.info(self.dir)
        vid_src =  "rtsp://{}:{}@{}:554/Streaming/Channels/1/".format(
            self.args.username,
            self.args.password,
            self.args.source,
        )
        cmd = 'ffmpeg -y -i "{}" -vf fps=1 -updatefirst 1 {}/screen.jpg'.format(
            vid_src,
            self.dir,
        )
        self.logger.info(cmd)
        self.streams = {
            'mjpg': subprocess.Popen(cmd, stdout=FNULL, stderr=subprocess.STDOUT, shell=True)
        }

    def get_snapshot(self):
        return "{}/screen.jpg".format(self.dir)

    def change_video_settings(self, options):
        tilt = (900*int(options['brightness']))/100
        pan = (3600*(100-int(options['contrast'])))/100
        zoom = (40*int(options['hue']))/100
        req = """<PTZData>
<AbsoluteHigh>
<elevation> {} </elevation>
<azimuth> {} </azimuth>
<absoluteZoom> {} </absoluteZoom>
</AbsoluteHigh>
</PTZData>
        """.format(tilt, pan, zoom)
        uri = "http://{}/ISAPI/PTZCtrl/channels/1/absolute".format(self.args.source)
        requests.put(uri, auth=HTTPDigestAuth(self.args.username, self.args.password), data=req)
        self.logger.info("Moving to %s:%s:%s", pan, tilt, zoom)
        pass

    def start_video_stream(self, stream_name, options):
        vid_src =  "rtsp://{}:{}@{}:554/Streaming/Channels/1/".format(
            self.args.username,
            self.args.password,
            self.args.source,
        )

        cmd = 'ffmpeg -y -i "{}" -vcodec copy -strict -2 -c:a aac -metadata streamname={} -f flv tcp://{}:6666/'.format(
            vid_src,
            stream_name,
            self.args.host,
        )
        self.logger.info("Spwaning ffmpeg: %s", cmd)
        if stream_name not in self.streams or self.streams[stream_name].poll() is not None:
            self.streams[stream_name] = subprocess.Popen(cmd, stdout=FNULL, stderr=subprocess.STDOUT, shell=True)
