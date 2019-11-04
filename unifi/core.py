# import asyncio
import json
import ssl
import time
import requests
import os
import threading
import websocket

OPCODE_DATA = (websocket.ABNF.OPCODE_TEXT, websocket.ABNF.OPCODE_BINARY)


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

    def gen_msg_id(self):
        self._msg_id += 1
        return self._msg_id

    def recv(self, ws):
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

    def init_adoption(self, ws):
        self.logger.info(
            "Initiating adoption with token [%s] and mac [%s]", self.token, self.mac
        )
        self.send(
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
                    "fwVersion": "UVC.S2L.v4.13.40.67.5c03e9e.190526.1445",
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
                },
                "messageId": self.gen_msg_id(),
                "inResponseTo": 0,
            },
        )

    def process_param_agreement(self, msg):
        return {
            "from": "ubnt_avclient",
            "functionName": "ubnt_avclient_paramAgreement",
            "inResponseTo": msg["messageId"],
            "messageId": self.gen_msg_id(),
            "payload": {"authToken": self.token},
            "responseExpected": False,
            "to": "UniFiVideo",
        }

    def process_isp_settings(self, msg):
        return {
            "from": "ubnt_avclient",
            "to": "UniFiVideo",
            "responseExpected": False,
            "functionName": "ResetIspSettings",
            "payload": {
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
            },
            "messageId": self.gen_msg_id(),
            "inResponseTo": msg["messageId"],
        }

    def process_video_settings(self, msg):
        # self.cam.set_video_settings(msg['payload'])
        vid_dst = {
            "video1": ["file:///dev/null"],
            "video2": ["file:///dev/null"],
            "video3": ["file:///dev/null"],
        }

        if msg["payload"] is not None:
            for k, v in msg["payload"]["video"].items():
                if v:
                    if "avSerializer" in v:
                        vid_dst[k] = v["avSerializer"]["destinations"]
                        if "parameters" in v["avSerializer"]:
                            self.streams[k] = stream = v["avSerializer"]["parameters"][
                                "streamName"
                            ]
                            self.cam.start_video_stream(stream, k)

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

    def process_device_settings(self, msg):
        return {
            "from": "ubnt_avclient",
            "to": "UniFiVideo",
            "responseExpected": False,
            "functionName": "ChangeDeviceSettings",
            "payload": {
                "name": self.name,
                "region": msg["payload"]["region"],
                "timezone": "PST8PDT,M3.2.0,M11.1.0",
            },
            "messageId": self.gen_msg_id(),
            "inResponseTo": msg["messageId"],
        }

    def process_osd_settings(self, msg):
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

    def process_network_status(self, msg):
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

    def process_sound_led_settings(self, msg):
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

    def process_change_isp_settings(self, msg):
        if msg["payload"]:
            self.cam.change_video_settings(msg["payload"])
        return {
            "from": "ubnt_avclient",
            "to": "UniFiVideo",
            "responseExpected": False,
            "functionName": "ChangeIspSettings",
            "payload": {
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
            },
            "messageId": self.gen_msg_id(),
            "inResponseTo": msg["messageId"],
        }

    def process_analytics_settings(self, msg):
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

    def process_snapshot_request(self, msg):
        path = self.cam.get_snapshot()
        while not os.path.isfile(path):
            time.sleep(0.1)
        files = {"payload": (msg["payload"]["filename"], open(path, "rb"))}
        requests.post(
            msg["payload"]["uri"],
            files=files,
            data=msg["payload"]["formFields"],
            cert=self.cert,
            verify=False,
        )

    def process_time(self, msg):
        return {
            "from": "ubnt_avclient",
            "functionName": "ubnt_avclient_paramAgreement",
            "inResponseTo": msg["messageId"],
            "messageId": self.gen_msg_id(),
            "payload": {
                "monotonicMs": self.get_uptime(),
                "wallMs": int(round(time.time() * 1000)),
            },
            "responseExpected": False,
            "to": "UniFiVideo",
        }

    def process_username_password(self, msg):
        return {
            "from": "ubnt_avclient",
            "functionName": "UpdateUsernamePassword",
            "inResponseTo": msg["messageId"],
            "messageId": self.gen_msg_id(),
            "payload": {},
            "responseExpected": False,
            "to": "UniFiVideo",
        }

    def get_uptime(self):
        return time.time() - self.init_time

    def send(self, ws, msg):
        self.logger.debug("Sending: %s", msg)
        ws.send_binary(json.dumps(msg))

    def process(self, ws, msg):
        m = json.loads(msg)
        self.logger.info("Processing [%s] message", m["functionName"])
        self.logger.debug("Message contents: %s", m)

        if m["responseExpected"] == False and m["functionName"] not in [
            "GetRequest",
            "UpdateFirmwareRequest",
        ]:
            return

        res = None
        if m["functionName"] == "ubnt_avclient_hello":
            pass
        elif m["functionName"] == "ubnt_avclient_timeSync":
            pass
        elif m["functionName"] == "ubnt_avclient_time":
            res = self.process_time(m)
        elif m["functionName"] == "ubnt_avclient_paramAgreement":
            res = self.process_param_agreement(m)
        elif m["functionName"] == "ResetIspSettings":
            res = self.process_isp_settings(m)
        elif m["functionName"] == "ChangeVideoSettings":
            res = self.process_video_settings(m)
        elif m["functionName"] == "ChangeDeviceSettings":
            res = self.process_device_settings(m)
        elif m["functionName"] == "ChangeOsdSettings":
            res = self.process_osd_settings(m)
        elif m["functionName"] == "NetworkStatus":
            res = self.process_network_status(m)
        elif m["functionName"] == "ChangeSoundLedSettings":
            res = self.process_sound_led_settings(m)
        elif m["functionName"] == "ChangeIspSettings":
            res = self.process_change_isp_settings(m)
        elif m["functionName"] == "ChangeAnalyticsSettings":
            res = self.process_analytics_settings(m)
        elif m["functionName"] == "GetRequest":
            self.process_snapshot_request(m)
        elif m["functionName"] == "UpdateUsernamePassword":
            res = self.process_username_password(m)
        elif m["functionName"] == "UpdateFirmwareRequest":
            return True

        if res is not None:
            self.send(ws, res)

        return False

    def send_pulse(self, ws):
        while True:
            if self.pulse_interval is not 0:
                time.sleep(self.pulse_interval)
                res = {
                    "from": "ubnt_avclient",
                    "to": "UniFiVideo",
                    "responseExpected": False,
                    "functionName": "EventAnalytics",
                    "payload": {
                        "clockBestMonotonic": 0,
                        "clockBestWall": 0,
                        "clockMonotonic": int(round(self.get_uptime())),
                        "clockWall": int(round(time.time() * 1000)),
                        "edgeType": "unknown",
                        "eventId": 9223372036854775807,
                        "eventType": "pulse",
                        "levels": {"0": 1},
                        "motionHeatmap": "",
                        "motionSnapshot": "",
                    },
                    "messageId": self.gen_msg_id(),
                    "inResponseTo": 0,
                }
                self.logger.info("Sending pulse...")
                self.send(ws, res)
            time.sleep(0.1)

    def run(self):
        uri = "wss://{}:7442/camera/1.0/ws?token={}".format(self.host, self.token)
        ssl_opts = {"cert_reqs": ssl.CERT_NONE, "certfile": self.cert}
        headers = {"camera-mac": self.mac}
        self.logger.info("Creating ws connection to %s", uri)

        while True:
            ws = websocket.create_connection(uri, sslopt=ssl_opts, header=headers)
            self.init_adoption(ws)

            self.pulse_thread = threading.Thread(target=self.send_pulse, args=(ws,))
            self.pulse_thread.daemon = True
            self.pulse_thread.start()

            while True:
                opcode, data = self.recv(ws)
                msg = None
                if opcode in OPCODE_DATA:
                    msg = data

                if msg is not None:
                    reconnect = self.process(ws, msg)
                    if reconnect:
                        self.logger.info("Reconnecting...")
                        break

                if opcode == websocket.ABNF.OPCODE_CLOSE:
                    break
