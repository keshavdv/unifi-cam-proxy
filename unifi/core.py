import asyncio
import json
import os
import ssl
import threading
import time
import urllib
from typing import Any, Dict, Optional, Tuple

import requests
import websocket

OPCODE_DATA = (websocket.ABNF.OPCODE_TEXT, websocket.ABNF.OPCODE_BINARY)

AVClientRequest = AVClientResponse = Dict[str, Any]


class Core(object):
    def __init__(self, args, camera, logger):
        self.host = args.host
        self.cert = args.cert
        self.token = args.token
        self.mac = args.mac
        self.name = args.name
        self.cam_ip = args.ip
        self.cam = camera
        self.logger = logger
        self._msg_id = 0
        self.init_time = time.time()
        self.pulse_interval = 0
        self.streams = {}
        self.version = "UVC.S2L.v4.23.8.67.0eba6e3.200526.1046"

    def gen_msg_id(self) -> int:
        self._msg_id += 1
        return self._msg_id

    def recv(self, ws) -> Tuple[int, Optional[bytes]]:
        try:
            frame = ws.recv_frame()
        except websocket.WebSocketException:
            return websocket.ABNF.OPCODE_CLOSE, None
        if not frame:
            raise websocket.WebSocketException("Not a valid frame %s" % frame)
        elif frame.opcode in OPCODE_DATA:
            return frame.opcode, frame.data
        elif frame.opcode == websocket.ABNF.OPCODE_CLOSE:
            ws.send_close()
            return frame.opcode, None
        elif frame.opcode == websocket.ABNF.OPCODE_PING:
            ws.pong(frame.data)
            return frame.opcode, frame.data

        return frame.opcode, frame.data

    async def init_adoption(self, ws) -> None:
        self.logger.info(
            "Initiating adoption with token [%s] and mac [%s]", self.token, self.mac
        )
        await self.send(
            ws,
            {
                "from": "ubnt_avclient",
                "to": "UniFiVideo",
                "responseExpected": False,
                "functionName": "ubnt_avclient_hello",
                "payload": {
                    "adoptionCode": self.token,
                    "connectionHost": self.host,
                    "connectionSecurePort": 7442,
                    "fwVersion": self.version,
                    "hwrev": 19,
                    "idleTime": 191.96,
                    "ip": self.cam_ip,
                    "mac": self.mac,
                    "model": "UVC G3",
                    "name": self.name,
                    "protocolVersion": 67,
                    "rebootTimeoutSec": 30,
                    "semver": "v4.4.8",
                    "totalLoad": 0.5474,
                    "upgradeTimeoutSec": 150,
                    "uptime": self.get_uptime(),
                    "features": {},
                },
                "messageId": self.gen_msg_id(),
                "inResponseTo": 0,
            },
        )

    async def process_param_agreement(self, msg: AVClientRequest) -> AVClientResponse:
        return {
            "from": "ubnt_avclient",
            "functionName": "ubnt_avclient_paramAgreement",
            "inResponseTo": msg["messageId"],
            "messageId": self.gen_msg_id(),
            "payload": {"authToken": self.token, "features": {}},
            "responseExpected": False,
            "to": "UniFiVideo",
        }

    async def process_upgrade(self, msg: AVClientRequest) -> None:
        url = msg["payload"]["uri"]
        headers = {"Range": "bytes=0-100"}
        r = requests.get(url, headers=headers, verify=False)

        # Parse the new version string from the upgrade binary
        version = ""
        for i in range(0, 50):
            b = r.content[4 + i]
            if b != b"\x00":
                version += chr(b)
        self.logger.debug("Pretending to upgrade to: %s", version)
        self.version = version
        return

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
        payload.update(self.cam.get_video_settings())
        return {
            "from": "ubnt_avclient",
            "to": "UniFiVideo",
            "responseExpected": False,
            "functionName": "ResetIspSettings",
            "payload": payload,
            "messageId": self.gen_msg_id(),
            "inResponseTo": msg["messageId"],
        }

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
                        if (
                            "parameters" in v["avSerializer"]
                            and "destinations" in v["avSerializer"]
                        ):
                            self.streams[k] = stream = v["avSerializer"]["parameters"][
                                "streamName"
                            ]
                            try:
                                host, port = urllib.parse.urlparse(
                                    v["avSerializer"]["destinations"][0]
                                ).netloc.split(":")
                                self.cam.start_video_stream(
                                    k, stream, destination=(host, port)
                                )
                            except ValueError:
                                pass

        return {
            "from": "ubnt_avclient",
            "to": "UniFiVideo",
            "responseExpected": False,
            "functionName": "ChangeVideoSettings",
            "payload": {
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
                            if "video1" not in self.streams
                            else {
                                "audioId": None,
                                "streamName": self.streams["video1"],
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
                        "height": 720,
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
                        "width": 1280,
                    },
                    "video2": {
                        "M": 1,
                        "N": 30,
                        "avSerializer": {
                            "destinations": vid_dst["video2"],
                            "parameters": None
                            if "video2" not in self.streams
                            else {
                                "audioId": None,
                                "streamName": self.streams["video2"],
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
                        "height": 400,
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
                        "width": 720,
                    },
                    "video3": {
                        "M": 1,
                        "N": 30,
                        "avSerializer": {
                            "destinations": vid_dst["video3"],
                            "parameters": None
                            if "video3" not in self.streams
                            else {
                                "audioId": None,
                                "streamName": self.streams["video3"],
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
            "messageId": self.gen_msg_id(),
            "inResponseTo": msg["messageId"],
        }

    async def process_device_settings(self, msg: AVClientRequest) -> AVClientResponse:
        return {
            "from": "ubnt_avclient",
            "to": "UniFiVideo",
            "responseExpected": False,
            "functionName": "ChangeDeviceSettings",
            "payload": {
                "name": self.name,
                "timezone": "PST8PDT,M3.2.0,M11.1.0",
            },
            "messageId": self.gen_msg_id(),
            "inResponseTo": msg["messageId"],
        }

    async def process_osd_settings(self, msg: AVClientRequest) -> AVClientResponse:
        return {
            "from": "ubnt_avclient",
            "to": "UniFiVideo",
            "responseExpected": False,
            "functionName": "ChangeOsdSettings",
            "payload": {
                "_1": {
                    "enableDate": 1,
                    "enableLogo": 1,
                    "enableReportdStatsLevel": 0,
                    "enableStreamerStatsLevel": 0,
                    "tag": self.name,
                },
                "_2": {
                    "enableDate": 1,
                    "enableLogo": 1,
                    "enableReportdStatsLevel": 0,
                    "enableStreamerStatsLevel": 0,
                    "tag": self.name,
                },
                "_3": {
                    "enableDate": 1,
                    "enableLogo": 1,
                    "enableReportdStatsLevel": 0,
                    "enableStreamerStatsLevel": 0,
                    "tag": self.name,
                },
                "_4": {
                    "enableDate": 1,
                    "enableLogo": 1,
                    "enableReportdStatsLevel": 0,
                    "enableStreamerStatsLevel": 0,
                    "tag": self.name,
                },
                "enableOverlay": 1,
                "logoScale": 50,
                "overlayColorId": 0,
                "textScale": 50,
                "useCustomLogo": 0,
            },
            "messageId": self.gen_msg_id(),
            "inResponseTo": msg["messageId"],
        }

    async def process_network_status(self, msg: AVClientRequest) -> AVClientResponse:
        return {
            "from": "ubnt_avclient",
            "to": "UniFiVideo",
            "responseExpected": False,
            "functionName": "NetworkStatus",
            "payload": {
                "connectionState": 2,
                "connectionStateDescription": "CONNECTED",
                "defaultInterface": "eth0",
                "dhcpLeasetime": 86400,
                "dnsServer": "8.8.8.8 4.2.2.2",
                "gateway": "192.168.103.1",
                "ipAddress": self.cam_ip,
                "linkDuplex": 1,
                "linkSpeedMbps": 100,
                "mode": "dhcp",
                "networkMask": "255.255.255.0",
            },
            "messageId": self.gen_msg_id(),
            "inResponseTo": msg["messageId"],
        }

    async def process_system_stats(self, msg: AVClientRequest) -> AVClientResponse:
        return {
            "from": "ubnt_avclient",
            "to": "UniFiVideo",
            "responseExpected": False,
            "functionName": "SystemStats",
            "payload": {
                "network": {
                    "bytesRx": 0,
                    "bytesTx": 0,
                },
                "battery": 0,
            },
            "messageId": self.gen_msg_id(),
            "inResponseTo": msg["messageId"],
        }

    async def process_sound_led_settings(
        self, msg: AVClientRequest
    ) -> AVClientResponse:
        return {
            "from": "ubnt_avclient",
            "to": "UniFiVideo",
            "responseExpected": False,
            "functionName": "ChangeSoundLedSettings",
            "payload": {
                "ledFaceAlwaysOnWhenManaged": 1,
                "ledFaceEnabled": 1,
                "speakerEnabled": 1,
                "speakerVolume": 100,
                "systemSoundsEnabled": 1,
                "userLedBlinkPeriodMs": 0,
                "userLedColorFg": "blue",
                "userLedOnNoff": 1,
            },
            "messageId": self.gen_msg_id(),
            "inResponseTo": msg["messageId"],
        }

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
            self.cam.change_video_settings(msg["payload"])

        payload.update(self.cam.get_video_settings())
        return {
            "from": "ubnt_avclient",
            "to": "UniFiVideo",
            "responseExpected": False,
            "functionName": "ChangeIspSettings",
            "payload": payload,
            "messageId": self.gen_msg_id(),
            "inResponseTo": msg["messageId"],
        }

    async def process_analytics_settings(
        self, msg: AVClientRequest
    ) -> AVClientResponse:
        if msg["payload"]["sendPulse"] is 1:
            self.pulse_interval = msg["payload"]["pulsePeriodSec"]
        else:
            self.pulse_interval = 0
        return {
            "from": "ubnt_avclient",
            "to": "UniFiVideo",
            "responseExpected": False,
            "functionName": "ChangeAnalyticsSettings",
            "payload": msg["payload"],
            "messageId": self.gen_msg_id(),
            "inResponseTo": msg["messageId"],
        }

    async def process_snapshot_request(
        self, msg: AVClientRequest
    ) -> Optional[AVClientResponse]:
        path = self.cam.get_snapshot()
        while not os.path.isfile(path):
            await asyncio.sleep(0.1)
        files = {
            "payload": (msg["payload"].get("filename", "snapshot"), open(path, "rb"))
        }
        requests.post(
            msg["payload"]["uri"],
            files=files,
            data=msg["payload"]["formFields"]
            if "formFields" in msg["payload"]
            else None,
            cert=self.cert,
            verify=False,
        )
        if msg["responseExpected"]:
            return {
                "from": "ubnt_avclient",
                "functionName": "GetRequest",
                "inResponseTo": msg["messageId"],
                "messageId": self.gen_msg_id(),
                "payload": {},
                "responseExpected": False,
                "to": "UniFiVideo",
            }

    async def process_time(self, msg: AVClientRequest) -> AVClientResponse:
        return {
            "from": "ubnt_avclient",
            "functionName": "ubnt_avclient_paramAgreement",
            "inResponseTo": msg["messageId"],
            "messageId": self.gen_msg_id(),
            "payload": {
                "monotonicMs": self.get_uptime(),
                "wallMs": int(round(time.time() * 1000)),
                "features": {},
            },
            "responseExpected": False,
            "to": "UniFiVideo",
        }

    async def process_username_password(self, msg: AVClientRequest) -> Dict[str, Any]:
        return {
            "from": "ubnt_avclient",
            "functionName": "UpdateUsernamePassword",
            "inResponseTo": msg["messageId"],
            "messageId": self.gen_msg_id(),
            "payload": {},
            "responseExpected": False,
            "to": "UniFiVideo",
        }

    def get_uptime(self) -> float:
        return time.time() - self.init_time

    async def send(self, ws, msg: AVClientRequest) -> None:
        self.logger.debug(f"Sending: {msg}")
        ws.send_binary(json.dumps(msg))

    async def process(self, ws, msg: bytes) -> bool:
        m = json.loads(msg)
        fn = m["functionName"]

        self.logger.info(f"Processing [{fn}] message")
        self.logger.debug(f"Message contents: {m}")

        if (
            ("responseExpected" not in m)
            or (m["responseExpected"] == False)
            and (
                fn not in ["GetRequest", "ChangeVideoSettings", "UpdateFirmwareRequest"]
            )
        ):
            return False

        res: Optional[AVClientResponse] = None

        if fn == "ubnt_avclient_hello":
            pass
        elif fn == "ubnt_avclient_timeSync":
            pass
        elif fn == "ubnt_avclient_time":
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
        elif fn == "GetSystemStats":
            res = await self.process_system_stats(m)
        elif fn == "ChangeSoundLedSettings":
            res = await self.process_sound_led_settings(m)
        elif fn == "ChangeIspSettings":
            res = await self.process_change_isp_settings(m)
        elif fn == "ChangeAnalyticsSettings":
            res = await self.process_analytics_settings(m)
        elif fn == "GetRequest":
            res = await self.process_snapshot_request(m)
        elif fn == "UpdateUsernamePassword":
            res = await self.process_username_password(m)
        elif fn == "UpdateFirmwareRequest":
            res = await self.process_upgrade(m)
            return True

        if res is not None:
            await self.send(ws, res)

        return False

    async def run(self) -> None:
        uri = "wss://{}:7442/camera/1.0/ws?token={}".format(self.host, self.token)
        ssl_opts = {"cert_reqs": ssl.CERT_NONE, "certfile": self.cert}
        headers = {"camera-mac": self.mac}
        self.logger.info("Creating ws connection to %s", uri)

        while True:
            try:
                ws = websocket.create_connection(
                    uri, sslopt=ssl_opts, header=headers, subprotocols=["secure_transfer"]
                )
            except websocket._exceptions.WebSocketException as e:
                if "Invalid WebSocket Header" in str(e):
                    self.logger.info("Falling back to UFV mode")
                    ws = websocket.create_connection(
                        uri, sslopt=ssl_opts, header=headers
                    )
            await self.init_adoption(ws)

            while True:
                opcode, data = self.recv(ws)
                msg = None
                if opcode in OPCODE_DATA:
                    msg = data

                if msg is not None:
                    reconnect = await self.process(ws, msg)
                    if reconnect:
                        self.logger.info("Reconnecting...")
                        break

                if opcode == websocket.ABNF.OPCODE_CLOSE:
                    break
