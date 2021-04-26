import tempfile

import aiohttp
import json

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
        img_file = "{}/screen.jpg".format(self.snapshot_dir)
        url = f"http://{self.args.ip}/api.cgi?cmd=Snap&user={self.args.username}&password={self.args.password}&rs=6PHVjvf0UntSLbyT&channel={self.args.channel}"
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
            f"http://{self.args.ip}/api.cgi?user={self.args.username}&password={self.args.password}",
            encoded=True,
        )

        body = f'[{{ "cmd":"GetMdState", "param":{{ "channel":{self.args.channel} }} }}]'
        while True:
            self.logger.info(f"Connecting to motion events API: {url}")
            try:
                async with aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(None)
                ) as session:
                  while True:
                    async with session.post(url, data=body) as resp:
                      data = await resp.read()
                      json_body = json.loads(data)

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

            except aiohttp.ClientError as err:
                self.logger.error(f"Motion API request failed, retrying. Error: {err}")

    def get_stream_source(self, stream_index: str):
      return f"rtsp://{self.args.username}:{self.args.password}@{self.args.ip}:554//h264Preview_{int(self.args.channel) + 1:02}_main"
