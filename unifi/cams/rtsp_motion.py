from aiohttp import web

from unifi.cams.rtsp import RTSPCam


class RTSPMotionCam(RTSPCam):
    def __init__(self, args, logger=None):
        super().__init__(args, logger)

    @classmethod
    def add_parser(self, parser):
        super().add_parser(parser)
        parser.add_argument(
            "--http-api",
            default=0,
            type=int,
            help="Specify a port number to enable the HTTP API",
        )

    async def run(self):
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
