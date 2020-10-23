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

```
pip install unifi-cam-proxy
scp ubnt@<your-unifi-cam>:/var/etc/persistent/server.pem client.pem
# RTSP stream
unifi-cam-proxy --host <NVR IP> --cert client.pem --token <Adoption token> rtsp -s rtsp://wowzaec2demo.streamlock.net/vod/mp4:BigBuckBunny_175k.mov
```

You can also create your own client certificate via:

```
openssl ecparam -out /tmp/private.key -name prime256v1 -genkey -noout
openssl req -new -sha256 -key /tmp/private.key -out /tmp/server.csr -subj "/C=TW/L=Taipei/O=Ubiquiti Networks Inc./OU=devint/CN=camera.ubnt.dev/emailAddress=support@ubnt.com"
openssl x509 -req -sha256 -days 36500 -in /tmp/server.csr -signkey /tmp/private.key -out /tmp/public.key
cat /tmp/private.key /tmp/public.key > client.pem
rm -f /tmp/private.key /tmp/public.key /tmp/server.csr
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
