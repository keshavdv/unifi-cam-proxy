import argparse
import asyncio
import logging
import tempfile
import time
from pathlib import Path
from typing import Any, Union

import httpx
import xmltodict
from hikvisionapi import AsyncClient

from unifi.cams.base import UnifiCamBase


class HikvisionCam(UnifiCamBase):
    def __init__(self, args: argparse.Namespace, logger: logging.Logger) -> None:
        super().__init__(args, logger)
        self.snapshot_dir = tempfile.mkdtemp()
        self.streams = {}
        self.cam = AsyncClient(
            f"http://{self.args.ip}",
            self.args.username,
            self.args.password,
            timeout=None,
        )
        self.channel = args.channel
        self.substream = args.substream
        self.ptz_supported = False
        self.motion_in_progress: bool = False
        self._last_event_timestamp: Union[str, int] = 0

    @classmethod
    def add_parser(cls, parser: argparse.ArgumentParser) -> None:
        super().add_parser(parser)
        parser.add_argument("--username", "-u", required=True, help="Camera username")
        parser.add_argument("--password", "-p", required=True, help="Camera password")
        parser.add_argument(
            "--channel", "-c", default=1, type=int, help="Camera channel index"
        )
        parser.add_argument(
            "--substream", "-s", default=3, type=int, help="Camera substream index"
        )

    async def get_snapshot(self) -> Path:
        img_file = Path(self.snapshot_dir, "screen.jpg")
        source = int(f"{self.channel}01")
        try:
            with img_file.open("wb") as f:
                async for chunk in self.cam.Streaming.channels[source].picture(
                    method="get", type="opaque_data"
                ):
                    if chunk:
                        f.write(chunk)
        except httpx.RequestError:
            pass
        return img_file

    async def check_ptz_support(self, channel) -> bool:
        try:
            await self.cam.PTZCtrl.channels[channel].capabilities(method="get")
            self.logger.info("Detected PTZ support")
            return True
        except (httpx.RequestError, httpx.HTTPStatusError):
            pass
        return False

    async def get_video_settings(self) -> dict[str, Any]:
        if self.ptz_supported:
            r = (await self.cam.PTZCtrl.channels[1].status(method="get"))["PTZStatus"][
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
        return {}

    async def change_video_settings(self, options: dict[str, Any]) -> None:
        if self.ptz_supported:
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
            await self.cam.PTZCtrl.channels[1].absolute(
                method="put", data=xmltodict.unparse(req, pretty=True)
            )

    async def get_stream_source(self, stream_index: str) -> str:
        substream = 1
        if stream_index != "video1":
            substream = self.substream

        return (
            f"rtsp://{self.args.username}:{self.args.password}@{self.args.ip}:554"
            f"/Streaming/Channels/{self.channel}0{substream}/"
        )

    async def maybe_end_motion_event(self, start_time):
        await asyncio.sleep(2)
        if self.motion_in_progress and self._last_event_timestamp == start_time:
            await self.trigger_motion_stop()
            self.motion_in_progress = False

    async def run(self) -> None:
        self.ptz_supported = await self.check_ptz_support(self.channel)
        return

        while True:
            self.logger.info("Connecting to motion events API")
            try:
                async for event in self.cam.Event.notification.alertStream(
                    method="get", type="stream", timeout=None
                ):
                    alert = event.get("EventNotificationAlert")
                    if (
                        alert
                        and alert.get("channelID") == str(self.channel)
                        and alert.get("eventType") == "VMD"
                    ):

                        self._last_event_timestamp = alert.get("dateTime", time.time())

                        if self.motion_in_progress is False:
                            self.motion_in_progress = True
                            await self.trigger_motion_start()

                        # End motion event after 2 seconds of no updates
                        asyncio.ensure_future(
                            self.maybe_end_motion_event(self._last_event_timestamp)
                        )
            except httpx.RequestError:
                self.logger.error("Motion API request failed, retrying")
