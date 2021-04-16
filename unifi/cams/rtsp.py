import subprocess
import tempfile

from aiohttp import web

from unifi.cams.base import UnifiCamBase


class RTSPCam(UnifiCamBase):
    def __init__(self, args, logger=None):
        super(RTSPCam, self).__init__(args, logger)
        self.args = args
        self.event_id = 0
        self.snapshot_dir = tempfile.mkdtemp()
        self.snapshot_stream = None
        self.runner = None

    @classmethod
    def add_parser(self, parser):
        super().add_parser(parser)
        parser.add_argument("--source", "-s", required=True, help="Stream source")
        parser.add_argument(
            "--http-api",
            default=0,
            type=int,
            help="Specify a port number to enable the HTTP API (default: disabled)",
        )

    async def get_snapshot(self):
        if not self.snapshot_stream or self.snapshot_stream.poll() is not None:
            cmd = f'ffmpeg -nostdin -y -re -rtsp_transport {self.args.rtsp_transport} -i "{self.args.source}" -vf fps=1 -update 1 {self.snapshot_dir}/screen.jpg'
            self.logger.info(f"Spawning stream for snapshots: {cmd}")
            self.snapshot_stream = subprocess.Popen(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=True
            )
        return "{}/screen.jpg".format(self.snapshot_dir)

    async def run(self):
        if self.args.http_api:
            self.logger.info(f"Enabling HTTP API on port {self.args.http_api}")

            app = web.Application()

            async def start_motion(request):
                self.logger.debug("Starting motion")
                await self.trigger_motion_start()
                return web.Response(text="ok")

            async def stop_motion(request):
                self.logger.debug("Starting motion")
                await self.trigger_motion_stop()
                return web.Response(text="ok")

            app.add_routes([web.get("/start_motion", start_motion)])
            app.add_routes([web.get("/stop_motion", stop_motion)])

            self.runner = web.AppRunner(app)
            await self.runner.setup()
            site = web.TCPSite(self.runner, port=self.args.http_api)
            await site.start()

    async def close(self):
        await super().close()
        if self.runner:
            await self.runner.cleanup()

        if self.snapshot_stream:
            self.snapshot_stream.kill()

    def get_stream_source(self, stream_index: str):
        return self.args.source
