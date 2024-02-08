import argparse
import logging
import subprocess
import tempfile
from pathlib import Path

from aiohttp import web

from unifi.cams.base import UnifiCamBase

from pytapo import Tapo


class TapoCam(UnifiCamBase):
    def __init__(self, args: argparse.Namespace, logger: logging.Logger) -> None:
        super().__init__(args, logger)
        self.args = args
        self.event_id = 0
        self.snapshot_dir = tempfile.mkdtemp()
        self.snapshot_stream = None
        self.runner = None
        self.stream_source = dict()
        self.stream_source["video1"] = self.args.rtsp + "/stream1"
        self.stream_source["video2"] = self.args.rtsp + "/stream1"
        self.stream_source["video3"] = self.args.rtsp + "/stream2"
        self.ptz_enabled = False
        self.cam = None

        try:
            self.cam = Tapo(self.args.ip, self.args.username, self.args.password)
            self.cam.getMotorCapability()
            self.ptz_enabled = True

        except AttributeError:
            self.logger.info("PTZ Not enabled because of insufficient configuration")

        except Exception:
            self.logger.info("PTZ Not enabled, not supportet for this camera")

        if not self.args.snapshot_url:
            self.start_snapshot_stream()

    @classmethod
    def add_parser(cls, parser: argparse.ArgumentParser) -> None:
        super().add_parser(parser)
        parser.add_argument(
            "--username",
            "-u",
            default="admin",
            help="Username (default:admin)"
        )
        parser.add_argument(
            "--password",
            "-p",
            help="Your TPlink app password"
        )
        parser.add_argument(
            "--rtsp",
            required=True,
            help="Your RTSP base URL (rtsp://camera_username:camera_password@192.168.172.180:554)"
        )
        parser.add_argument(
            "--http-api",
            default=0,
            type=int,
            help="Specify a port number to enable the HTTP API (default: disabled)",
        )
        parser.add_argument(
            "--snapshot-url",
            "-i",
            default=None,
            type=str,
            required=False,
            help="HTTP endpoint to fetch snapshot image from",
        )

    def start_snapshot_stream(self) -> None:
        if not self.snapshot_stream or self.snapshot_stream.poll() is not None:
            cmd = (
                f"ffmpeg -nostdin -y -re -rtsp_transport {self.args.rtsp_transport} "
                f'-i "{self.stream_source["video3"]}" '
                "-r 1 "
                f"-update 1 {self.snapshot_dir}/screen.jpg"
            )
            self.logger.info(f"Spawning stream for snapshots: {cmd}")
            self.snapshot_stream = subprocess.Popen(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=True
            )

    async def get_snapshot(self) -> Path:
        img_file = Path(self.snapshot_dir, "screen.jpg")
        if self.args.snapshot_url:
            await self.fetch_to_file(self.args.snapshot_url, img_file)
        else:
            self.start_snapshot_stream()
        return img_file

    #this gets called when settings are updated on the unifi ui
    async def change_video_settings(self, options) -> None:
        if self.ptz_enabled:
            self.cam = Tapo(self.args.ip, self.args.username, self.args.password)
            #move down
            if int(options["brightness"]) < 20:
                self.logger.info("Moving down")
                self.cam.moveMotor(0, -10)
            #move up
            if int(options["brightness"]) > 80:
                self.logger.info("Moving up")
                self.cam.moveMotor(0, 10)
            #move left
            if int(options["contrast"]) > 80:
                self.logger.info("Moving right")
                self.cam.moveMotor(10, 0)
            #move right
            if int(options["contrast"]) < 20:
                self.logger.info("Moving left")
                self.cam.moveMotor(-10, 0)


    async def run(self) -> None:
        if self.ptz_enabled:
            self.logger.debug("PTZ Enabled")
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

    async def close(self) -> None:
        await super().close()
        if self.runner:
            await self.runner.cleanup()

        if self.snapshot_stream:
            self.snapshot_stream.kill()

    async def get_stream_source(self, stream_index: str) -> str:
        return self.stream_source[stream_index]
