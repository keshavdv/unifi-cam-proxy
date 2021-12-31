import argparse
import logging
import tempfile
from pathlib import Path

import aiohttp
from yarl import URL
from asyncio import sleep

from unifi.cams.base import UnifiCamBase
from unifi.util import DigestAuth


class DahuaCam(UnifiCamBase):
    def __init__(self, args: argparse.Namespace, logger: logging.Logger) -> None:
        super().__init__(args, logger)
        self._run_iteration = 1
        self.snapshot_dir = tempfile.mkdtemp()
        if self.args.snapshot_channel is None:
            self.args.snapshot_channel = self.args.channel - 1
        if self.args.motion_index is None:
            self.args.motion_index = self.args.snapshot_channel

    @classmethod
    def add_parser(cls, parser: argparse.ArgumentParser) -> None:
        super().add_parser(parser)
        parser.add_argument(
            "--username",
            "-u",
            required=True,
            help="Camera username",
        )
        parser.add_argument(
            "--password",
            "-p",
            required=True,
            help="Camera password",
        )
        parser.add_argument(
            "--channel",
            "-c",
            required=False,
            type=int,
            default=1,
            help="Camera channel",
        )
        parser.add_argument(
            "--snapshot-channel",
            required=False,
            type=int,
            default=None,
            help="Snapshot channel",
        )
        parser.add_argument(
            "--main-stream",
            required=False,
            type=int,
            default=0,
            help="Main Stream subtype index",
        )
        parser.add_argument(
            "--sub-stream",
            required=False,
            type=int,
            default=1,
            help="Sub Stream subtype index",
        )
        parser.add_argument(
            "--motion-index",
            required=False,
            type=int,
            default=None,
            help="VideoMotion event index",
        )

    async def get_snapshot(self) -> Path:
        img_file = Path(self.snapshot_dir, "screen.jpg")
        url = f"http://{self.args.ip}/cgi-bin/snapshot.cgi?channel={self.args.snapshot_channel}"
        
        try:
            async with aiohttp.ClientSession() as session:
                auth = DigestAuth(self.args.username, self.args.password, session)
                async with await auth.request("GET", url) as resp:
                    with img_file.open("wb") as f:
                        f.write(await resp.read())
                        return img_file
        except aiohttp.ClientError:
            return img_file

    async def run(self) -> None:

        if self.args.motion_index == -1:
            return
        url = f"http://{self.args.ip}/cgi-bin/eventManager.cgi?action=attach&codes=[VideoMotion]"
        encoded_url = URL(url, encoded=True)

        # Keep track of multiple calls of run(),
        # since the same instance will be used across multiple reboots.
        # When expected_iteration no longer matches _run_iteration,
        # we know we need to stop retrying because there's a new while loop
        # that's taken over.
        expected_iteration = self._run_iteration
        while expected_iteration == self._run_iteration:
            self.logger.info(f"Connecting to motion events API: {url}")
            try:
                async with aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(None)
                ) as session:
                    self._motion_session = session
                    # Some (or maybe all?) cams need digest auth.
                    # I modified this to also perform basic auth depending on the server response.
                    # (https://github.com/keshavdv/unifi-cam-proxy/issues/74#issuecomment-913289921):
                    auth = DigestAuth(self.args.username, self.args.password, session)
                    
                    async with await auth.request("GET", encoded_url) as resp:
                        if resp.status != 200:
                            self.logger.error(
                                f"Motion API unsupported (status: {resp.status})"
                            )
                            await sleep(10)
                            continue

                        # The multipart respones on this endpoint
                        # are not properly formatted, so this
                        # is implemented manually
                        while not resp.content.at_eof():
                            line = (await resp.content.readline()).decode()
                            # self.logger.debug(line.strip())
                            if line.startswith("Code="):
                                parts = line.split(";")
                                action = parts[1].split("=")[1].strip()
                                index = parts[2].split("=")[1].strip()
                                if index != f"{self.args.motion_index}":
                                    continue
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
                await sleep(10)

    def get_stream_source(self, stream_index: str) -> str:

        if stream_index == "video1":
            subtype = self.args.main_stream
        else:
            subtype = self.args.sub_stream

        return (
            f"rtsp://{self.args.username}:{self.args.password}@{self.args.ip}"
            f"/cam/realmonitor?channel={self.args.channel}&subtype={subtype}"
        )

    async def close(self):
        self._run_iteration = self._run_iteration + 1
        if self._motion_session:
            await self._motion_session.close()
        await super().close()
