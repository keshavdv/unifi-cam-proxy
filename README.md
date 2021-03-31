UniFi Camera Proxy
==================

## Note: This does not currently work with UniFi Protect (UDMP/UNVR) devices, only the older UniFi Video installations

About
-----

This enables using non-Ubiquiti cameras within the UniFi Video software. This is
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
* Python2.7 only (due to flvlib dependency)


Usage
-----

In order to use this, you must own at least one UniFi camera in order to obtain a valid client certificate (Found at `/var/etc/persistent/server.pem` via SSH).

```
pip install unifi-cam-proxy
scp ubnt@<your-unifi-cam>:/var/etc/persistent/server.pem client.pem
# RTSP stream
unifi-cam-proxy --host <NVR IP> --cert client.pem --token <Adoption token> rtsp -s rtsp://wowzaec2demo.streamlock.net/vod/mp4:BigBuckBunny_175k.mov
```


Hikvision PTZ (Hikvision DS-2DE3304W-DE):

```
unifi-cam-proxy -H <NVR IP> -i <camera IP> -c client.pem -t <Adoption token> hikvision -u <username> -p <password>
```

Multiple Cameras
----
To deploy multiple cameras, run multiple instances of the proxy, taking care to specify different MAC addressess:

```
unifi-cam-proxy --host <NVR IP> --mac 'AA:BB:CC:00:11:22' --cert client.pem --token <Adoption token> rtsp -s rtsp://camera1
unifi-cam-proxy --host <NVR IP> --mac 'AA:BB:CC:33:44:55' --cert client.pem --token <Adoption token> rtsp -s rtsp://camera2
```
