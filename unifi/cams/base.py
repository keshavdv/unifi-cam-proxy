import argparse
import atexit
import json
import logging
import shutil
import ssl
import subprocess
import sys
import tempfile
import time
import urllib
from abc import ABCMeta, abstractmethod
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import aiohttp
import websockets

from unifi.core import RetryableError

AVClientRequest = AVClientResponse = Dict[str, Any]


class SmartDetectObjectType(Enum):
    PERSON = "person"
    VEHICLE = "vehicle"


class UnifiCamBase(metaclass=ABCMeta):
    def __init__(self, args: argparse.Namespace, logger: logging.Logger) -> None:
        self.args = args
        self.logger = logger

        self._msg_id: int = 0
        self._init_time: float = time.time()
        self._streams: Dict[str, str] = {}
        self._motion_snapshot: Optional[Path] = None
        self._motion_event_id: int = 0
        self._motion_event_ts: Optional[float] = None
        self._motion_object_type: Optional[SmartDetectObjectType] = None
        self._ffmpeg_handles: Dict[str, subprocess.Popen] = {}

        # Set up ssl context for requests
        self._ssl_context = ssl.create_default_context()
        self._ssl_context.check_hostname = False
        self._ssl_context.verify_mode = ssl.CERT_NONE
        self._ssl_context.load_cert_chain(args.cert, args.cert)
        self._session: Optional[websockets.legacy.client.WebSocketClientProtocol] = None
        atexit.register(self.close_streams)

    @classmethod
    def add_parser(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--ffmpeg-args",
            "-f",
            default="-c:v copy -ar 32000 -ac 1 -codec:a aac -b:a 32k",
            help="Transcoding args for `ffmpeg -i <src> <args> <dst>`",
        )
        parser.add_argument(
            "--rtsp-transport",
            default="tcp",
            choices=["tcp", "udp", "http", "udp_multicast"],
            help="RTSP transport protocol used by stream",
        )

    async def _run(self, ws) -> None:
        self._session = ws
        await self.init_adoption()
        while True:
            try:
                msg = await ws.recv()
            except websockets.exceptions.ConnectionClosedError:
                self.logger.info(f"Connection to {self.args.host} was closed.")
                raise RetryableError()

            if msg is not None:
                force_reconnect = await self.process(msg)
                if force_reconnect:
                    self.logger.info("Reconnecting...")
                    raise RetryableError()

    async def run(self) -> None:
        pass

    async def get_video_settings(self) -> Dict[str, Any]:
        return {}

    async def change_video_settings(self, options) -> None:
        pass

    @abstractmethod
    async def get_snapshot(self) -> Path:
        raise NotImplementedError("You need to write this!")

    @abstractmethod
    async def get_stream_source(self, stream_index: str) -> str:
        raise NotImplementedError("You need to write this!")

    def get_extra_ffmpeg_args(self, stream_index: str = "") -> str:
        return self.args.ffmpeg_args

    async def get_feature_flags(self) -> Dict[str, Any]:
        return {
            "mic": True,
            "aec": [],
            "videoMode": ["default"],
            "motionDetect": ["enhanced"],
        }

    # API for subclasses
    async def trigger_motion_start(
        self, object_type: Optional[SmartDetectObjectType] = None
    ) -> None:
        if not self._motion_event_ts:
            payload: Dict[str, Any] = {
                "clockBestMonotonic": 0,
                "clockBestWall": 0,
                "clockMonotonic": int(self.get_uptime()),
                "clockStream": int(self.get_uptime()),
                "clockStreamRate": 1000,
                "clockWall": int(round(time.time() * 1000)),
                "edgeType": "start",
                "eventId": self._motion_event_id,
                "eventType": "motion",
                "levels": {"0": 47},
                "motionHeatmap": "",
                "motionSnapshot": "",
            }
            if object_type:
                payload.update(
                    {
                        "objectTypes": [object_type.value],
                        "edgeType": "enter",
                        "zonesStatus": {"0": 48},
                        "smartDetectSnapshot": "",
                    }
                )

            self.logger.info(
                f"Triggering motion start (idx: {self._motion_event_id})"
                + f" for {object_type.value}"
                if object_type
                else ""
            )
            await self.send(
                self.gen_response(
                    "EventSmartDetect" if object_type else "EventAnalytics",
                    payload=payload,
                ),
            )
            self._motion_event_ts = time.time()
            self._motion_object_type = object_type

            # Capture snapshot at beginning of motion event for thumbnail
            motion_snapshot_path: str = tempfile.NamedTemporaryFile(delete=False).name
            try:
                shutil.copyfile(await self.get_snapshot(), motion_snapshot_path)
                self.logger.debug(f"Captured motion snapshot to {motion_snapshot_path}")
                self._motion_snapshot = Path(motion_snapshot_path)
            except FileNotFoundError:
                pass

    async def trigger_motion_stop(self) -> None:
        motion_start_ts = self._motion_event_ts
        motion_object_type = self._motion_object_type
        if motion_start_ts:
            payload: Dict[str, Any] = {
                "clockBestMonotonic": int(self.get_uptime()),
                "clockBestWall": int(round(motion_start_ts * 1000)),
                "clockMonotonic": int(self.get_uptime()),
                "clockStream": int(self.get_uptime()),
                "clockStreamRate": 1000,
                "clockWall": int(round(time.time() * 1000)),
                "edgeType": "stop",
                "eventId": self._motion_event_id,
                "eventType": "motion",
                "levels": {"0": 49},
                "motionHeatmap": "heatmap.png",
                "motionSnapshot": "motionsnap.jpg",
            }
            if motion_object_type:
                payload.update(
                    {
                        "objectTypes": [motion_object_type.value],
                        "edgeType": "leave",
                        "zonesStatus": {"0": 48},
                        "smartDetectSnapshot": "motionsnap.jpg",
                    }
                )
            self.logger.info(
                f"Triggering motion stop (idx: {self._motion_event_id})"
                + f" for {motion_object_type.value}"
                if motion_object_type
                else ""
            )
            await self.send(
                self.gen_response(
                    "EventSmartDetect" if motion_object_type else "EventAnalytics",
                    payload=payload,
                ),
            )
            self._motion_event_id += 1
            self._motion_event_ts = None
            self._motion_object_type = None

    def update_motion_snapshot(self, path: Path) -> None:
        self._motion_snapshot = path

    async def fetch_to_file(self, url: str, dst: Path) -> bool:
        try:
            async with aiohttp.request("GET", url) as resp:
                if resp.status != 200:
                    self.logger.error(f"Error retrieving file {resp.status}")
                    return False
                with dst.open("wb") as f:
                    f.write(await resp.read())
                    return True
        except aiohttp.ClientError:
            return False

    # Protocol implementation
    def gen_msg_id(self) -> int:
        self._msg_id += 1
        return self._msg_id

    async def init_adoption(self) -> None:
        self.logger.info(
            f"Adopting with token [{self.args.token}] and mac [{self.args.mac}]"
        )
        await self.send(
            self.gen_response(
                "ubnt_avclient_hello",
                payload={
                    "adoptionCode": self.args.token,
                    "connectionHost": self.args.host,
                    "connectionSecurePort": 7442,
                    "fwVersion": self.args.fw_version,
                    "hwrev": 19,
                    "idleTime": 191.96,
                    "ip": self.args.ip,
                    "mac": self.args.mac,
                    "model": self.args.model,
                    "name": self.args.name,
                    "protocolVersion": 67,
                    "rebootTimeoutSec": 30,
                    "semver": "v4.4.8",
                    "totalLoad": 0.5474,
                    "upgradeTimeoutSec": 150,
                    "uptime": int(self.get_uptime()),
                    "features": await self.get_feature_flags(),
                },
            ),
        )

    async def process_param_agreement(self, msg: AVClientRequest) -> AVClientResponse:
        return self.gen_response(
            "ubnt_avclient_paramAgreement",
            msg["messageId"],
            {
                "authToken": self.args.token,
                "features": await self.get_feature_flags(),
            },
        )

    async def process_upgrade(self, msg: AVClientRequest) -> None:
        url = msg["payload"]["uri"]
        headers = {"Range": "bytes=0-100"}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, ssl=False) as r:
                # Parse the new version string from the upgrade binary
                content = await r.content.readexactly(54)
                version = ""
                for i in range(0, 50):
                    b = content[4 + i]
                    if b != b"\x00":
                        version += chr(b)
                self.logger.debug(f"Pretending to upgrade to: {version}")
                self.args.fw_version = version

    async def process_isp_settings(self, msg: AVClientRequest) -> AVClientResponse:
        payload = {
            "aeMode": "auto",
            "aeTargetPercent": 50,
            "aggressiveAntiFlicker": 0,
            "brightness": 50,
            "contrast": 50,
            "criticalTmpOfProtect": 40,
            "darkAreaCompensateLevel": 0,
            "denoise": 50,
            "enable3dnr": 1,
            "enableMicroTmpProtect": 1,
            "enablePauseMotion": 0,
            "flip": 0,
            "focusMode": "ztrig",
            "focusPosition": 0,
            "forceFilterIrSwitchEvents": 0,
            "hue": 50,
            "icrLightSensorNightThd": 0,
            "icrSensitivity": 0,
            "irLedLevel": 215,
            "irLedMode": "auto",
            "irOnStsBrightness": 0,
            "irOnStsContrast": 0,
            "irOnStsDenoise": 0,
            "irOnStsHue": 0,
            "irOnStsSaturation": 0,
            "irOnStsSharpness": 0,
            "irOnStsWdr": 0,
            "irOnValBrightness": 50,
            "irOnValContrast": 50,
            "irOnValDenoise": 50,
            "irOnValHue": 50,
            "irOnValSaturation": 50,
            "irOnValSharpness": 50,
            "irOnValWdr": 1,
            "mirror": 0,
            "queryIrLedStatus": 0,
            "saturation": 50,
            "sharpness": 50,
            "touchFocusX": 1001,
            "touchFocusY": 1001,
            "wdr": 1,
            "zoomPosition": 0,
        }
        payload.update(await self.get_video_settings())
        return self.gen_response(
            "ResetIspSettings",
            msg["messageId"],
            payload,
        )

    async def process_video_settings(self, msg: AVClientRequest) -> AVClientResponse:
        vid_dst = {
            "video1": ["file:///dev/null"],
            "video2": ["file:///dev/null"],
            "video3": ["file:///dev/null"],
        }

        if msg["payload"] is not None and "video" in msg["payload"]:
            for k, v in msg["payload"]["video"].items():
                if v:
                    if "avSerializer" in v:
                        vid_dst[k] = v["avSerializer"]["destinations"]
                        if "/dev/null" in vid_dst[k]:
                            self.stop_video_stream(k)
                        elif "parameters" in v["avSerializer"]:
                            self._streams[k] = stream = v["avSerializer"]["parameters"][
                                "streamName"
                            ]
                            try:
                                host, port = urllib.parse.urlparse(
                                    v["avSerializer"]["destinations"][0]
                                ).netloc.split(":")
                                await self.start_video_stream(
                                    k, stream, destination=(host, int(port))
                                )
                            except ValueError:
                                pass

        return self.gen_response(
            "ChangeVideoSettings",
            msg["messageId"],
            {
                "audio": {
                    "bitRate": 32000,
                    "channels": 1,
                    "description": "audio track",
                    "enableTemporalNoiseShaping": False,
                    "enabled": True,
                    "mode": 0,
                    "quality": 0,
                    "sampleRate": 11025,
                    "type": "aac",
                    "volume": 100,
                },
                "firmwarePath": "/lib/firmware/",
                "video": {
                    "enableHrd": False,
                    "hdrMode": 0,
                    "lowDelay": False,
                    "videoMode": "default",
                    "mjpg": {
                        "avSerializer": {
                            "destinations": [
                                "file:///tmp/snap.jpeg",
                                "file:///tmp/snap_av.jpg",
                            ],
                            "parameters": {
                                "audioId": 1000,
                                "enableTimestampsOverlapAvoidance": False,
                                "suppressAudio": True,
                                "suppressVideo": False,
                                "videoId": 1001,
                            },
                            "type": "mjpg",
                        },
                        "bitRateCbrAvg": 500000,
                        "bitRateVbrMax": 500000,
                        "bitRateVbrMin": None,
                        "description": "JPEG pictures",
                        "enabled": True,
                        "fps": 5,
                        "height": 720,
                        "isCbr": False,
                        "maxFps": 5,
                        "minClientAdaptiveBitRate": 0,
                        "minMotionAdaptiveBitRate": 0,
                        "nMultiplier": None,
                        "name": "mjpg",
                        "quality": 80,
                        "sourceId": 3,
                        "streamId": 8,
                        "streamOrdinal": 3,
                        "type": "mjpg",
                        "validBitrateRangeMax": 6000000,
                        "validBitrateRangeMin": 32000,
                        "width": 1280,
                    },
                    "video1": {
                        "M": 1,
                        "N": 30,
                        "avSerializer": {
                            "destinations": vid_dst["video1"],
                            "parameters": None
                            if "video1" not in self._streams
                            else {
                                "audioId": None,
                                "streamName": self._streams["video1"],
                                "suppressAudio": None,
                                "suppressVideo": None,
                                "videoId": None,
                            },
                            "type": "extendedFlv",
                        },
                        "bitRateCbrAvg": 1400000,
                        "bitRateVbrMax": 2800000,
                        "bitRateVbrMin": 48000,
                        "description": "Hi quality video track",
                        "enabled": True,
                        "fps": 15,
                        "gopModel": 0,
                        "height": 1080,
                        "horizontalFlip": False,
                        "isCbr": False,
                        "maxFps": 30,
                        "minClientAdaptiveBitRate": 0,
                        "minMotionAdaptiveBitRate": 0,
                        "nMultiplier": 6,
                        "name": "video1",
                        "sourceId": 0,
                        "streamId": 1,
                        "streamOrdinal": 0,
                        "type": "h264",
                        "validBitrateRangeMax": 2800000,
                        "validBitrateRangeMin": 32000,
                        "validFpsValues": [
                            1,
                            2,
                            3,
                            4,
                            5,
                            6,
                            8,
                            9,
                            10,
                            12,
                            15,
                            16,
                            18,
                            20,
                            24,
                            25,
                            30,
                        ],
                        "verticalFlip": False,
                        "width": 1920,
                    },
                    "video2": {
                        "M": 1,
                        "N": 30,
                        "avSerializer": {
                            "destinations": vid_dst["video2"],
                            "parameters": None
                            if "video2" not in self._streams
                            else {
                                "audioId": None,
                                "streamName": self._streams["video2"],
                                "suppressAudio": None,
                                "suppressVideo": None,
                                "videoId": None,
                            },
                            "type": "extendedFlv",
                        },
                        "bitRateCbrAvg": 500000,
                        "bitRateVbrMax": 1200000,
                        "bitRateVbrMin": 48000,
                        "currentVbrBitrate": 1200000,
                        "description": "Medium quality video track",
                        "enabled": True,
                        "fps": 15,
                        "gopModel": 0,
                        "height": 720,
                        "horizontalFlip": False,
                        "isCbr": False,
                        "maxFps": 30,
                        "minClientAdaptiveBitRate": 0,
                        "minMotionAdaptiveBitRate": 0,
                        "nMultiplier": 6,
                        "name": "video2",
                        "sourceId": 1,
                        "streamId": 2,
                        "streamOrdinal": 1,
                        "type": "h264",
                        "validBitrateRangeMax": 1500000,
                        "validBitrateRangeMin": 32000,
                        "validFpsValues": [
                            1,
                            2,
                            3,
                            4,
                            5,
                            6,
                            8,
                            9,
                            10,
                            12,
                            15,
                            16,
                            18,
                            20,
                            24,
                            25,
                            30,
                        ],
                        "verticalFlip": False,
                        "width": 1280,
                    },
                    "video3": {
                        "M": 1,
                        "N": 30,
                        "avSerializer": {
                            "destinations": vid_dst["video3"],
                            "parameters": None
                            if "video3" not in self._streams
                            else {
                                "audioId": None,
                                "streamName": self._streams["video3"],
                                "suppressAudio": None,
                                "suppressVideo": None,
                                "videoId": None,
                            },
                            "type": "extendedFlv",
                        },
                        "bitRateCbrAvg": 300000,
                        "bitRateVbrMax": 200000,
                        "bitRateVbrMin": 48000,
                        "currentVbrBitrate": 200000,
                        "description": "Low quality video track",
                        "enabled": True,
                        "fps": 15,
                        "gopModel": 0,
                        "height": 360,
                        "horizontalFlip": False,
                        "isCbr": False,
                        "maxFps": 30,
                        "minClientAdaptiveBitRate": 0,
                        "minMotionAdaptiveBitRate": 0,
                        "nMultiplier": 6,
                        "name": "video3",
                        "sourceId": 2,
                        "streamId": 4,
                        "streamOrdinal": 2,
                        "type": "h264",
                        "validBitrateRangeMax": 750000,
                        "validBitrateRangeMin": 32000,
                        "validFpsValues": [
                            1,
                            2,
                            3,
                            4,
                            5,
                            6,
                            8,
                            9,
                            10,
                            12,
                            15,
                            16,
                            18,
                            20,
                            24,
                            25,
                            30,
                        ],
                        "verticalFlip": False,
                        "width": 640,
                    },
                    "vinFps": 30,
                },
            },
        )

    async def process_device_settings(self, msg: AVClientRequest) -> AVClientResponse:
        return self.gen_response(
            "ChangeDeviceSettings",
            msg["messageId"],
            {
                "name": self.args.name,
                "timezone": "PST8PDT,M3.2.0,M11.1.0",
            },
        )

    async def process_osd_settings(self, msg: AVClientRequest) -> AVClientResponse:
        return self.gen_response(
            "ChangeOsdSettings",
            msg["messageId"],
            {
                "_1": {
                    "enableDate": 1,
                    "enableLogo": 1,
                    "enableReportdStatsLevel": 0,
                    "enableStreamerStatsLevel": 0,
                    "tag": self.args.name,
                },
                "_2": {
                    "enableDate": 1,
                    "enableLogo": 1,
                    "enableReportdStatsLevel": 0,
                    "enableStreamerStatsLevel": 0,
                    "tag": self.args.name,
                },
                "_3": {
                    "enableDate": 1,
                    "enableLogo": 1,
                    "enableReportdStatsLevel": 0,
                    "enableStreamerStatsLevel": 0,
                    "tag": self.args.name,
                },
                "_4": {
                    "enableDate": 1,
                    "enableLogo": 1,
                    "enableReportdStatsLevel": 0,
                    "enableStreamerStatsLevel": 0,
                    "tag": self.args.name,
                },
                "enableOverlay": 1,
                "logoScale": 50,
                "overlayColorId": 0,
                "textScale": 50,
                "useCustomLogo": 0,
            },
        )

    async def process_network_status(self, msg: AVClientRequest) -> AVClientResponse:
        return self.gen_response(
            "NetworkStatus",
            msg["messageId"],
            {
                "connectionState": 2,
                "connectionStateDescription": "CONNECTED",
                "defaultInterface": "eth0",
                "dhcpLeasetime": 86400,
                "dnsServer": "8.8.8.8 4.2.2.2",
                "gateway": "192.168.103.1",
                "ipAddress": self.args.ip,
                "linkDuplex": 1,
                "linkSpeedMbps": 100,
                "mode": "dhcp",
                "networkMask": "255.255.255.0",
            },
        )

    async def process_sound_led_settings(
        self, msg: AVClientRequest
    ) -> AVClientResponse:
        return self.gen_response(
            "ChangeSoundLedSettings",
            msg["messageId"],
            {
                "ledFaceAlwaysOnWhenManaged": 1,
                "ledFaceEnabled": 1,
                "speakerEnabled": 1,
                "speakerVolume": 100,
                "systemSoundsEnabled": 1,
                "userLedBlinkPeriodMs": 0,
                "userLedColorFg": "blue",
                "userLedOnNoff": 1,
            },
        )

    async def process_change_isp_settings(
        self, msg: AVClientRequest
    ) -> AVClientResponse:
        payload = {
            "aeMode": "auto",
            "aeTargetPercent": 50,
            "aggressiveAntiFlicker": 0,
            "brightness": 50,
            "contrast": 50,
            "criticalTmpOfProtect": 40,
            "dZoomCenterX": 50,
            "dZoomCenterY": 50,
            "dZoomScale": 0,
            "dZoomStreamId": 4,
            "darkAreaCompensateLevel": 0,
            "denoise": 50,
            "enable3dnr": 1,
            "enableExternalIr": 0,
            "enableMicroTmpProtect": 1,
            "enablePauseMotion": 0,
            "flip": 0,
            "focusMode": "ztrig",
            "focusPosition": 0,
            "forceFilterIrSwitchEvents": 0,
            "hue": 50,
            "icrLightSensorNightThd": 0,
            "icrSensitivity": 0,
            "irLedLevel": 215,
            "irLedMode": "auto",
            "irOnStsBrightness": 0,
            "irOnStsContrast": 0,
            "irOnStsDenoise": 0,
            "irOnStsHue": 0,
            "irOnStsSaturation": 0,
            "irOnStsSharpness": 0,
            "irOnStsWdr": 0,
            "irOnValBrightness": 50,
            "irOnValContrast": 50,
            "irOnValDenoise": 50,
            "irOnValHue": 50,
            "irOnValSaturation": 50,
            "irOnValSharpness": 50,
            "irOnValWdr": 1,
            "lensDistortionCorrection": 1,
            "masks": None,
            "mirror": 0,
            "queryIrLedStatus": 0,
            "saturation": 50,
            "sharpness": 50,
            "touchFocusX": 1001,
            "touchFocusY": 1001,
            "wdr": 1,
            "zoomPosition": 0,
        }

        if msg["payload"]:
            await self.change_video_settings(msg["payload"])

        payload.update(await self.get_video_settings())
        return self.gen_response("ChangeIspSettings", msg["messageId"], payload)

    async def process_analytics_settings(
        self, msg: AVClientRequest
    ) -> AVClientResponse:
        return self.gen_response(
            "ChangeAnalyticsSettings", msg["messageId"], msg["payload"]
        )

    async def process_snapshot_request(
        self, msg: AVClientRequest
    ) -> Optional[AVClientResponse]:
        snapshot_type = msg["payload"]["what"]
        if snapshot_type in ["motionSnapshot", "smartDetectZoneSnapshot"]:
            path = self._motion_snapshot
        else:
            path = await self.get_snapshot()

        if path and path.exists():
            async with aiohttp.ClientSession() as session:
                files = {"payload": open(path, "rb")}
                files.update(msg["payload"].get("formFields", {}))
                try:
                    await session.post(
                        msg["payload"]["uri"],
                        data=files,
                        ssl=self._ssl_context,
                    )
                    self.logger.debug(f"Uploaded {snapshot_type} from {path}")
                except aiohttp.ClientError:
                    self.logger.exception("Failed to upload snapshot")
        else:
            self.logger.warning(
                f"Snapshot file {path} is not ready yet, skipping upload"
            )

        if msg["responseExpected"]:
            return self.gen_response("GetRequest", response_to=msg["messageId"])

    async def process_time(self, msg: AVClientRequest) -> AVClientResponse:
        return self.gen_response(
            "ubnt_avclient_paramAgreement",
            msg["messageId"],
            {
                "monotonicMs": self.get_uptime(),
                "wallMs": int(round(time.time() * 1000)),
                "features": {},
            },
        )

    def gen_response(
        self, name: str, response_to: int = 0, payload: Optional[Dict[str, Any]] = None
    ) -> AVClientResponse:
        if not payload:
            payload = {}
        return {
            "from": "ubnt_avclient",
            "functionName": name,
            "inResponseTo": response_to,
            "messageId": self.gen_msg_id(),
            "payload": payload,
            "responseExpected": False,
            "to": "UniFiVideo",
        }

    def get_uptime(self) -> float:
        return time.time() - self._init_time

    async def send(self, msg: AVClientRequest) -> None:
        self.logger.debug(f"Sending: {msg}")
        ws = self._session
        if ws:
            await ws.send(json.dumps(msg).encode())

    async def process(self, msg: bytes) -> bool:
        m = json.loads(msg)
        fn = m["functionName"]

        self.logger.info(f"Processing [{fn}] message")
        self.logger.debug(f"Message contents: {m}")

        if (
            ("responseExpected" not in m)
            or (m["responseExpected"] is False)
            and (
                fn
                not in [
                    "GetRequest",
                    "ChangeVideoSettings",
                    "UpdateFirmwareRequest",
                    "Reboot",
                ]
            )
        ):
            return False

        res: Optional[AVClientResponse] = None

        if fn == "ubnt_avclient_time":
            res = await self.process_time(m)
        elif fn == "ubnt_avclient_paramAgreement":
            res = await self.process_param_agreement(m)
        elif fn == "ResetIspSettings":
            res = await self.process_isp_settings(m)
        elif fn == "ChangeVideoSettings":
            res = await self.process_video_settings(m)
        elif fn == "ChangeDeviceSettings":
            res = await self.process_device_settings(m)
        elif fn == "ChangeOsdSettings":
            res = await self.process_osd_settings(m)
        elif fn == "NetworkStatus":
            res = await self.process_network_status(m)
        elif fn == "AnalyticsTest":
            res = self.gen_response("AnalyticsTest", response_to=m["messageId"])
        elif fn == "ChangeSoundLedSettings":
            res = await self.process_sound_led_settings(m)
        elif fn == "ChangeIspSettings":
            res = await self.process_change_isp_settings(m)
        elif fn == "ChangeAnalyticsSettings":
            res = await self.process_analytics_settings(m)
        elif fn == "GetRequest":
            res = await self.process_snapshot_request(m)
        elif fn == "UpdateUsernamePassword":
            res = self.gen_response(
                "UpdateUsernamePassword", response_to=m["messageId"]
            )
        elif fn == "ChangeSmartDetectSettings":
            res = self.gen_response(
                "ChangeSmartDetectSettings", response_to=m["messageId"]
            )
        elif fn == "UpdateFirmwareRequest":
            await self.process_upgrade(m)
            return True
        elif fn == "Reboot":
            return True

        if res is not None:
            await self.send(res)

        return False

    def get_base_ffmpeg_args(self, stream_index: str = "") -> str:
        base_args = [
            "-avoid_negative_ts",
            "make_zero",
            "-fflags",
            "+genpts+discardcorrupt",
            "-use_wallclock_as_timestamps 1",
        ]

        try:
            output = subprocess.check_output(["ffmpeg", "-h", "full"])
            if b"stimeout" in output:
                base_args.append("-stimeout 15000000")
            else:
                base_args.append("-timeout 15000000")
        except subprocess.CalledProcessError:
            self.logger.exception("Could not check for ffmpeg options")

        return " ".join(base_args)

    async def start_video_stream(
        self, stream_index: str, stream_name: str, destination: Tuple[str, int]
    ):
        has_spawned = stream_index in self._ffmpeg_handles
        is_dead = has_spawned and self._ffmpeg_handles[stream_index].poll() is not None

        if not has_spawned or is_dead:
            source = await self.get_stream_source(stream_index)
            cmd = (
                f"ffmpeg -nostdin -loglevel error -y {self.get_base_ffmpeg_args(stream_index)}"
                f" -rtsp_transport {self.args.rtsp_transport}"
                f' -i "{source}" {self.get_extra_ffmpeg_args(stream_index)}'
                f" -metadata streamname={stream_name} -f flv -"
                f" | {sys.executable} -m unifi.clock_sync"
                f" | nc {destination[0]} {destination[1]}"
            )

            if is_dead:
                self.logger.warn(f"Previous ffmpeg process for {stream_index} died.")

            self.logger.info(
                f"Spawning ffmpeg for {stream_index} ({stream_name}): {cmd}"
            )
            self._ffmpeg_handles[stream_index] = subprocess.Popen(
                cmd, stdout=subprocess.DEVNULL, shell=True
            )

    def stop_video_stream(self, stream_index: str):
        if stream_index in self._ffmpeg_handles:
            self.logger.info(f"Stopping stream {stream_index}")
            self._ffmpeg_handles[stream_index].kill()

    async def close(self):
        self.logger.info("Cleaning up instance")
        await self.trigger_motion_stop()
        self.close_streams()

    def close_streams(self):
        for stream in self._ffmpeg_handles:
            self.stop_video_stream(stream)
