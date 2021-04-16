import tempfile

import aiohttp
from yarl import URL

from unifi.cams.base import UnifiCamBase


class LorexCam(UnifiCamBase):
    @classmethod
    def add_parser(self, parser):
        super(LorexCam, self).add_parser(parser)
        parser.add_argument("--username", "-u", required=True, help="Camera username")
        parser.add_argument("--password", "-p", required=True, help="Camera password")

    def __init__(self, args, logger=None):
        super().__init__(args, logger)
        self.snapshot_dir = tempfile.mkdtemp()

    async def get_snapshot(self):
        img_file = "{}/screen.jpg".format(self.snapshot_dir)
        url = f"http://{self.args.username}:{self.args.password}@{self.args.ip}/cgi-bin/snapshot.cgi"
        try:
            async with aiohttp.request("GET", url) as resp:
                with open(img_file, "wb") as f:
                    while True:
                        chunk = await resp.content.read(1024)
                        if not chunk:
                            break
                        f.write(chunk)
        except aiohttp.ClientError:
            self.logger.error("Failed to get snapshot")
        return img_file

    async def run(self):
        url = URL(
            f"http://{self.args.username}:{self.args.password}@{self.args.ip}/cgi-bin/eventManager.cgi?action=attach&codes=[VideoMotion]",
            encoded=True,
        )
        while True:
            self.logger.info(f"Connecting to motion events API: {url}")
            try:
                async with aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(None)
                ) as session:
                    async with session.request("GET", url) as resp:
                        while True:
                            line = (await resp.content.readline()).decode()
                            if line.startswith("Code="):
                                parts = line.split(";")
                                action = parts[1].split("=")[1].strip()
                                index = parts[2].split("=")[1].strip()
                                if action == "Start":
                                    self.logger.info(
                                        f"Trigger motion start for index {index}"
                                    )
                                    await self.trigger_motion_start()
                                elif action == "Stop":
                                    self.logger.info(
                                        f"Trigger motion end for index {index}"
                                    )
                                    await self.trigger_motion_stop()
            except aiohttp.ClientError:
                self.logger.error("Motion API request failed, retrying")

    def get_stream_source(self, stream_index: str):
        channel = 0
        if stream_index != "video1":
            channel = 2

        return f"rtsp://{self.args.username}:{self.args.password}@{self.args.ip}/cam/realmonitor?channel=1&subtype={channel}"
