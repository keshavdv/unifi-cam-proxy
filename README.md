UniFi Camera Proxy
==================
## About

This enables using non-Ubiquiti cameras within the UniFi Video/Protect software. This is
particularly useful to view existing RTSP-enabled cameras in the same UI and
mobile app.

Things that work:
* Live streaming
* Full-time recording
* Motion detection
* Smart Detections with [Frigate](https://github.com/blakeblackshear/frigate)

## Installation

Dependencies:

* ffmpeg and netcat must be installed
* Python 3+


## Usage

In order to use this, you must own at least one UniFi camera in order to obtain a valid client certificate (Found at `/var/etc/persistent/server.pem` via SSH).

#### Running natively
```
pip install unifi-cam-proxy
scp ubnt@<your-unifi-cam>:/var/etc/persistent/server.pem client.pem
# RTSP stream
unifi-cam-proxy --host <NVR IP> --cert client.pem --token <Adoption token> rtsp -s rtsp://wowzaec2demo.streamlock.net/vod/mp4:BigBuckBunny_175k.mov
```

#### Running with Docker
```
docker run --rm -v "/full/path/to/cert.pem:/client.pem" keshavdv/unifi-cam-proxy unifi-cam-proxy --verbose --ip "<Camera IP>" --host <NVR IP> --cert /client.pem --token <Adoption token> lorex -u rtsp -s rtsp://wowzaec2demo.streamlock.net/vod/mp4:BigBuckBunny_175k.mov
```

## Acquiring adoption token

#### Unifi Protect
1. On the Protect UI, click 'Add Devices' and select 'G3 Micro'. Select 'Continue on Web' and type in a random string for the SSID and Password fields and click 'Generate QR Code'
2. Take a screenshot of the QR code and upload it to https://zxing.org/w/decode.jspx
3. Decode the QR code and extract the token from the second to last line in the 'Raw Text' field.

#### Unifi Video

Follow the 'Token Adoption' step from [here](https://help.ui.com/hc/en-us/articles/204975924-UniFi-Video-How-to-Adopt-a-Remote-Camera-that-is-not-Displaying-in-the-NVR) to generate a new token


## Multiple Cameras
To deploy multiple cameras, run multiple instances of the proxy, taking care to specify different MAC addressess:

```
unifi-cam-proxy --host <NVR IP> --mac 'AA:BB:CC:00:11:22' --cert client.pem --token <Adoption token> rtsp -s rtsp://camera1
unifi-cam-proxy --host <NVR IP> --mac 'AA:BB:CC:33:44:55' --cert client.pem --token <Adoption token> rtsp -s rtsp://camera2
```


## Device-specific Implementations

1. Hikvision PTZ (Hikvision DS-2DE3304W-DE): Uses brightness/contrast settings to control PTZ
```
unifi-cam-proxy -H <NVR IP> -i <camera IP> -c client.pem -t <Adoption token> hikvision -u <username> -p <password>
```

2. Reolink NVR Cameras (Reolink RLN16-410): Adds motion events
Note: Camera/channel IDs are zero-based
```
unifi-cam-proxy -H <NVR IP> -i <camera IP> -c client.pem -t <Adoption token> reolink_nvr -u <username> -p <password> -c <camera_id>
```

3. Lorex (LNB4321B, likely also Dahua cameras): Adds motion events
```
unifi-cam-proxy -H <NVR IP> -i <camera IP> -c client.pem -t <Adoption token> lorex -u <username> -p <password>
```
