import argparse
import asyncio
import json
import logging
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

from asyncio_mqtt import Client

from unifi.cams.base import SmartDetectObjectType
from unifi.cams.rtsp import RTSPCam


class FrigateCam(RTSPCam):
    def __init__(self, args: argparse.Namespace, logger: logging.Logger) -> None:
        super().__init__(args, logger)
        self.args = args
        self.event_active: bool = False
        self.event_label: Optional[str] = None
        self.event_snapshot_ready = None

    @classmethod
    def add_parser(cls, parser: argparse.ArgumentParser) -> None:
        super().add_parser(parser)
        parser.add_argument("--mqtt-host", required=True, help="MQTT server")
        parser.add_argument("--mqtt-port", default=1883, type=int, help="MQTT server")
        parser.add_argument(
            "--mqtt-prefix", default="frigate", type=str, help="Topic prefix"
        )
        parser.add_argument(
            "--frigate-camera",
            required=True,
            type=str,
            help="Name of camera in frigate",
        )

    def get_feature_flags(self) -> Dict[str, Any]:
        return {
            **super().get_feature_flags(),
            **{
                "mic": True,
                "smartDetect": [
                    "person",
                    "vehicle",
                ],
            },
        }

    @classmethod
    def label_to_object_type(cls, label: str) -> Optional[SmartDetectObjectType]:
        if label == "person":
            return SmartDetectObjectType.PERSON
        elif label == "car":
            return SmartDetectObjectType.CAR

    async def run(self) -> None:
        async with Client(self.args.mqtt_host, port=self.args.mqtt_port) as client:
            self.logger.info(
                f"Connected to {self.args.mqtt_host}:{self.args.mqtt_port}"
            )
            tasks = [
                self.handle_detection_events(client),
                self.handle_snapshot_events(client),
            ]
            await client.subscribe(f"{self.args.mqtt_prefix}/#")
            await asyncio.gather(*tasks)

    async def handle_detection_events(self, client) -> None:
        async with client.filtered_messages(
            f"{self.args.mqtt_prefix}/events"
        ) as messages:
            async for message in messages:
                msg = message.payload.decode()
                try:
                    frigate_msg = json.loads(message.payload.decode())
                    if not frigate_msg["after"]["camera"] == self.args.frigate_camera:
                        return

                    label = frigate_msg["after"]["label"]
                    object_type = self.label_to_object_type(label)
                    if not object_type:
                        self.logger.warning(
                            f"Received unsupport detection label type: {label}"
                        )

                    if not self.event_active and frigate_msg["type"] == "new":
                        self.event_active = True
                        self.event_label = label
                        self.event_snapshot_ready = asyncio.Event()
                        await self.trigger_motion_start(object_type)
                    elif self.event_active and frigate_msg["type"] == "end":
                        # Wait for the best snapshot to be ready before
                        # ending the motion event
                        await self.event_snapshot_ready.wait()
                        await self.trigger_motion_stop(object_type)
                        self.event_active = False
                        self.event_label = None
                except json.JSONDecodeError:
                    self.logger.exception(f"Could not decode payload: {msg}")

    async def handle_snapshot_events(self, client) -> None:
        topic_fmt = f"{self.args.mqtt_prefix}/{self.args.frigate_camera}/{{}}/snapshot"
        self.logger.debug(topic_fmt.format("+"))
        async with client.filtered_messages(topic_fmt.format("+")) as messages:
            async for message in messages:
                if (
                    self.event_active
                    and not message.retain
                    and message.topic == topic_fmt.format(self.event_label)
                ):
                    f = tempfile.NamedTemporaryFile()
                    f.write(message.payload)
                    self.logger.debug(
                        f"Updating snapshot for {self.event_label} with {f.name}"
                    )
                    self.update_motion_snapshot(Path(f.name))
                    self.event_snapshot_ready.set()
                else:
                    self.logger.debug(
                        f"Discarding snapshot message ({len(message.payload)})"
                    )
