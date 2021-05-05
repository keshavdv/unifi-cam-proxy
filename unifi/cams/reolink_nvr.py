import json
import tempfile
from pathlib import Path

import aiohttp
from yarl import URL

from unifi.cams.base import UnifiCamBase


class ReolinkNVRCam(UnifiCamBase):
    @classmethod
    def add_parser(self, parser):
        super(ReolinkNVRCam, self).add_parser(parser)
        parser.add_argument("--username", "-u", required=True, help="NVR username")
        parser.add_argument("--password", "-p", required=True, help="NVR password")
        parser.add_argument("--channel", "-c", required=True, help="NVR camera channel")

    def __init__(self, args, logger=None):
        super().__init__(args, logger)
        self.snapshot_dir = tempfile.mkdtemp()
        self.motion_in_progress = False

    async def get_snapshot(self):
        img_file = Path(self.snapshot_dir, "screen.jpg")
        url = (
            f"http://{self.args.ip}"
            f"/api.cgi?cmd=Snap&user={self.args.username}&password={self.args.password}"
            f"&rs=6PHVjvf0UntSLbyT&channel={self.args.channel}"
        )
        await self.fetch_to_file(url, img_file)
        return img_file

    async def run(self):
        url = (
            f"http://{self.args.ip}"
            f"/api.cgi?user={self.args.username}&password={self.args.password}"
        )
        encoded_url = URL(url, encoded=True)

        body = (
            f'[{{ "cmd":"GetMdState", "param":{{ "channel":{self.args.channel} }} }}]'
        )
        while True:
            self.logger.info(f"Connecting to motion events API: {url}")
            try:
                async with aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(None)
                ) as session:
                    while True:
                        async with session.post(encoded_url, data=body) as resp:
                            data = await resp.read()

                            try:
                                json_body = json.loads(data)
                                if "value" in json_body[0]:
                                    if json_body[0]["value"]["state"] == 1:
                                        if not self.motion_in_progress:
                                            self.motion_in_progress = True
                                            self.logger.info("Trigger motion start")
                                            await self.trigger_motion_start()
                                    elif json_body[0]["value"]["state"] == 0:
                                        if self.motion_in_progress:
                                            self.motion_in_progress = False
                                            self.logger.info("Trigger motion end")
                                            await self.trigger_motion_stop()
                                else:
                                    self.logger.error(
                                        "Motion API request responded with "
                                        "unexpected JSON, retrying. "
                                        f"JSON: {data}"
                                    )

                            except json.JSONDecodeError as err:
                                self.logger.error(
                                    "Motion API request returned invalid "
                                    "JSON, retrying. "
                                    f"Error: {err}, "
                                    f"Response: {data}"
                                )

            except aiohttp.ClientError as err:
                self.logger.error(f"Motion API request failed, retrying. Error: {err}")

    def get_stream_source(self, stream_index: str):
        return (
            f"rtsp://{self.args.username}:{self.args.password}@{self.args.ip}:554"
            f"/h264Preview_{int(self.args.channel) + 1:02}_main"
        )
