import argparse
import asyncio
import json
import logging
import tempfile
from pathlib import Path
from typing import Any, Optional

import backoff
from asyncio_mqtt import Client
from asyncio_mqtt.error import MqttError

from unifi.cams.base import SmartDetectObjectType
from unifi.cams.rtsp import RTSPCam


class FrigateCam(RTSPCam):
    def __init__(self, args: argparse.Namespace, logger: logging.Logger) -> None:
        super().__init__(args, logger)
        self.args = args
        self.event_id: Optional[str] = None
        self.event_label: Optional[str] = None
        self.event_snapshot_ready = None

    @classmethod
    def add_parser(cls, parser: argparse.ArgumentParser) -> None:
        super().add_parser(parser)
        parser.add_argument("--mqtt-host", required=True, help="MQTT server")
        parser.add_argument("--mqtt-port", default=1883, type=int, help="MQTT server")
        parser.add_argument("--mqtt-username", required=False)
        parser.add_argument("--mqtt-password", required=False)
        parser.add_argument(
            "--mqtt-prefix", default="frigate", type=str, help="Topic prefix"
        )
        parser.add_argument(
            "--frigate-camera",
            required=True,
            type=str,
            help="Name of camera in frigate",
        )

    async def get_feature_flags(self) -> dict[str, Any]:
        return {
            **await super().get_feature_flags(),
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
        elif label in {"vehicle", "car", "motorcycle", "bus"}:
            return SmartDetectObjectType.VEHICLE

    async def run(self) -> None:
        has_connected = False

        @backoff.on_predicate(backoff.expo, max_value=60, logger=self.logger)
        async def mqtt_connect():
            nonlocal has_connected
            try:
                async with Client(
                    self.args.mqtt_host,
                    port=self.args.mqtt_port,
                    username=self.args.mqtt_username,
                    password=self.args.mqtt_password,
                ) as client:
                    has_connected = True
                    self.logger.info(
                        f"Connected to {self.args.mqtt_host}:{self.args.mqtt_port}"
                    )
                    tasks = [
                        self.handle_detection_events(client),
                        self.handle_snapshot_events(client),
                    ]
                    await client.subscribe(f"{self.args.mqtt_prefix}/#")
                    await asyncio.gather(*tasks)
            except MqttError:
                if not has_connected:
                    raise

        await mqtt_connect()

    async def handle_detection_events(self, client) -> None:
        async with client.filtered_messages(
            f"{self.args.mqtt_prefix}/events"
        ) as messages:
            async for message in messages:
                msg = message.payload.decode()
                try:
                    frigate_msg = json.loads(message.payload.decode())
                    if not frigate_msg["after"]["camera"] == self.args.frigate_camera:
                        continue

                    label = frigate_msg["after"]["label"]
                    object_type = self.label_to_object_type(label)
                    if not object_type:
                        self.logger.warning(
                            f"Received unsupported detection label type: {label}"
                        )

                    if not self.event_id and frigate_msg["type"] == "new":
                        self.event_id = frigate_msg["after"]["id"]
                        self.event_label = label
                        self.event_snapshot_ready = asyncio.Event()
                        self.logger.info(
                            f"Starting {self.event_label} motion event"
                            f" (id: {self.event_id})"
                        )
                        await self.trigger_motion_start(object_type)
                    elif (
                        self.event_id == frigate_msg["after"]["id"]
                        and frigate_msg["type"] == "end"
                    ):
                        # Wait for the best snapshot to be ready before
                        # ending the motion event
                        self.logger.info(f"Awaiting snapshot (id: {self.event_id})")
                        await self.event_snapshot_ready.wait()
                        self.logger.info(
                            f"Ending {self.event_label} motion event"
                            f" (id: {self.event_id})"
                        )
                        await self.trigger_motion_stop()
                        self.event_id = None
                        self.event_label = None
                except json.JSONDecodeError:
                    self.logger.exception(f"Could not decode payload: {msg}")

    async def handle_snapshot_events(self, client) -> None:
        topic_fmt = f"{self.args.mqtt_prefix}/{self.args.frigate_camera}/{{}}/snapshot"
        async with client.filtered_messages(topic_fmt.format("+")) as messages:
            async for message in messages:
                if (
                    self.event_id
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
