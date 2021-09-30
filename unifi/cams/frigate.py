import argparse
import asyncio
import json
import logging
from typing import Any, Dict, Optional

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
        self.motion_start: int = None
        self.motion_stop: int = None

    @classmethod
    def add_parser(cls, parser: argparse.ArgumentParser) -> None:
        super().add_parser(parser)
        parser.add_argument("--frigate-host", required=True, help="Frigate server")
        parser.add_argument("--frigate-port", default=5000, type=int, help="Frigate server")
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
        parser.add_argument(
            "--frigate-zone",
            type=str,
            help="Name of zone in frigate",
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
        has_connected = False

        @backoff.on_predicate(backoff.expo, max_value=60, logger=self.logger)
        async def mqtt_connect():
            nonlocal has_connected
            try:
                async with Client(
                    self.args.mqtt_host, port=self.args.mqtt_port
                ) as client:
                    has_connected = True
                    self.logger.info(
                        f"Connected to {self.args.mqtt_host}:{self.args.mqtt_port}"
                    )
                    tasks = [
                        self.handle_detection_events(client),
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
                            f"Received unsupport detection label type: {label}"
                        )
                    if not self.event_id and frigate_msg["type"] == "new":
                        self.event_id = frigate_msg["after"]["id"]
                        self.event_label = label
                        await self.handle_snapshot_events()
                    elif frigate_msg["type"] == "end":
                        self.event_id = frigate_msg["after"]["id"]
                        self.motion_start = int(round(frigate_msg["after"]["start_time"] * 1000))
                        self.motion_stop = int(round(frigate_msg["after"]["end_time"] * 1000))

                        if (
                            self.args.frigate_zone
                        ):
                            if self.args.frigate_zone not in frigate_msg["after"]["entered_zones"]:
                                object_type = None

                        await self.trigger_motion_start(object_type, self.motion_start)

                        # Wait for the best snapshot to be ready before
                        # ending the motion event
                        self.logger.info(f"Awaiting snapshot (id: {self.event_id})")
                        self.event_label = label
                        await self.handle_snapshot_events()

                        self.logger.info(
                            f"Ending {self.event_label} motion event"
                            f" (id: {self.event_id})"
                        )
                        await self.trigger_motion_stop(object_type, self.motion_stop)
                        self.event_id = None
                        self.event_label = None
                except json.JSONDecodeError:
                    self.logger.exception(f"Could not decode payload: {msg}")

    async def handle_snapshot_events(self):
        if self.event_id:
            f = self._motion_snapshot

            url = (
                f"http://{self.args.frigate_host}:{self.args.frigate_port}"
                f"/api/events/{self.event_id}/thumbnail.jpg"
            )

            await self.fetch_to_file(url, f)

            self.logger.debug(
                f"Updating snapshot for {self.event_label} using {url}"
            )
            self.update_motion_snapshot(f)
