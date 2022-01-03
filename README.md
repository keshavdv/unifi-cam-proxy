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
* Python 3.7+


## Usage

In order to use this, you'll need a client certificate. This can be acquired in one of two ways:

1. If you have a UniFi camera: `scp ubnt@<your-unifi-cam>:/var/etc/persistent/server.pem client.pem`
2. You can also create your own client certificate via:

```
openssl ecparam -out /tmp/private.key -name prime256v1 -genkey -noout
openssl req -new -sha256 -key /tmp/private.key -out /tmp/server.csr -subj "/C=TW/L=Taipei/O=Ubiquiti Networks Inc./OU=devint/CN=camera.ubnt.dev/emailAddress=support@ubnt.com"
openssl x509 -req -sha256 -days 36500 -in /tmp/server.csr -signkey /tmp/private.key -out /tmp/public.key
cat /tmp/private.key /tmp/public.key > client.pem
rm -f /tmp/private.key /tmp/public.key /tmp/server.csr
```

#### Running natively
```
pip install unifi-cam-proxy
# RTSP stream
unifi-cam-proxy --host <NVR IP> --cert client.pem --token <Adoption token> rtsp -s rtsp://wowzaec2demo.streamlock.net/vod/mp4:BigBuckBunny_175k.mov
```

#### Running with Docker
```
docker run --rm -v "/full/path/to/cert.pem:/client.pem" keshavdv/unifi-cam-proxy unifi-cam-proxy --verbose --ip "<Camera IP>" --host <NVR IP> --cert /client.pem --token <Adoption token> rtsp -s rtsp://wowzaec2demo.streamlock.net/vod/mp4:BigBuckBunny_175k.mov
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


## Brand-specific Instructions

#### Hikvision
  * Tested: Hikvision DS-2DE3304W-DE (Uses brightness/contrast settings to control PTZ movements)
```
unifi-cam-proxy -H <NVR IP> -i <camera IP> -c client.pem -t <Adoption token> hikvision -u <username> -p <password>
```

#### Reolink:
* Standalone cameras
    * Tested: RLC-410-5MP 
```
unifi-cam-proxy -H <NVR IP> -i <camera IP> -c client.pem -t <Adoption token> rtsp -s <rtsp stream> --ffmpeg-args='-c:v copy -bsf:v "h264_metadata=tick_rate=60000/1001:fixed_frame_rate_flag=1" -ar 32000 -ac 2 -codec:a aac -b:a 32k'

```
* Standalone cameras using proper Snapshot URL and Motion-Det API url using Camera Substream (main or sub) *work in progress*

Main camera stream example
```
unifi-cam-proxy -H <NVR IP> -i <camera IP> -c client.pem -t <Adoption token> reolink -u <username> -p <password> -s main --ffmpeg-args='-c:v copy -bsf:v "h264_metadata=tick_rate=60000/1001:fixed_frame_rate_flag=1" -ar 32000 -ac 2 -codec:a aac -b:a 32k'
```
Sub camera stream example
```
unifi-cam-proxy -H <NVR IP> -i <camera IP> -c client.pem -t <Adoption token> reolink -u <username> -p <password> -s sub --ffmpeg-args='-c:v copy -bsf:v "h264_metadata=tick_rate=30000/1001:fixed_frame_rate_flag=1" -an'
```
* (Note: Camera/channel arguments are either -s main, or -s sub. The substream is limited to a maximum 15fps so note the tick_rate in the example)

Reolink NVR
* NVR (Note: Camera/channel IDs are zero-based)
```
unifi-cam-proxy -H <NVR IP> -i <camera IP> -c client.pem -t <Adoption token> reolink_nvr -u <username> -p <password> -c <camera_id>
```

#### Lorex:
  * Tested: LNB4321B (supports motion events)
```
unifi-cam-proxy -H <NVR IP> -i <camera IP> -c client.pem -t <Adoption token> lorex -u <username> -p <password>
```

#### Frigate: Supports smart detections
  * Note: Do not use the RTMP stream from frigate, use the original RTSP stream from your camera
```
unifi-cam-proxy  -H <NVR IP> -i <camera IP> -c client.pem -t <Adoption token>  frigate -s <rtsp source> --mqtt-host <mqtt host> --frigate-camera <Name of camera in frigate>

```
