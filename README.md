UniFi Camera Proxy
==================

About
-----

This enables using non-Ubiquiti cameras within the UniFi NVR software. This is
particularly useful to view existing RTSP-enabled cameras in the same UI and
mobile app.

Things that work:
* Live stream
* Full-time recording

Things that don't work:
* Motion detection


Installation
------------

Dependencies:

* ffmpeg and netcat must be installed
* Python2.7 only


Usage
-----

In order to use this, you must own at least one UniFi camera in order to obtain a valid client certificate (Found at `/var/etc/persistent/server.pem` via SSH).

RTSP stream:

```
unifi-cam-proxy --host <NVR IP> --cert client.pem --token uQfUPROZxbkPszvR rtsp -s rtsp://wowzaec2demo.streamlock.net/vod/mp4:BigBuckBunny_175k.mov
```
Hikvision PTZ (Hikvision DS-2DE3304W-DE):

```
unifi-cam-proxy -H <NVR IP> -i <camera IP> -c client.pem -t <Adoption token> hikvision -u <username> -p <password>
```
