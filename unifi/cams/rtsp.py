import subprocess
import tempfile

from unifi.cams.base import UnifiCamBase


class RTSPCam(UnifiCamBase):
    def __init__(self, args, logger=None):
        super(RTSPCam, self).__init__(args, logger)
        self.args = args
        self.event_id = 0
        self.snapshot_dir = tempfile.mkdtemp()
        self.snapshot_stream = None

    @classmethod
    def add_parser(self, parser):
        super().add_parser(parser)
        parser.add_argument("--source", "-s", required=True, help="Stream source")

    async def get_snapshot(self):
        if not self.snapshot_stream or self.snapshot_stream.poll() is not None:
            cmd = f'ffmpeg -nostdin -y -re -rtsp_transport {self.args.rtsp_transport} -i "{self.args.source}" -vf fps=1 -update 1 {self.snapshot_dir}/screen.jpg'
            self.logger.info(f"Spawning stream for snapshots: {cmd}")
            self.snapshot_stream = subprocess.Popen(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=True
            )
        return "{}/screen.jpg".format(self.snapshot_dir)

    async def close(self):
        await super().close()
        if self.snapshot_stream:
            self.snapshot_stream.kill()

    def get_stream_source(self, stream_index: str):
        return self.args.source
