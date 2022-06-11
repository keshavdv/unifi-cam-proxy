---
sidebar_position: 1
---

# RTSP


Most generic cameras are supported via the RTSP integration. Depending on your camera, you might need specific flags to make live-streaming smoother, so check for your specific camera model in the docs before trying this.

```
unifi-cam-proxy -H {NVR IP} -i {Camera IP} -c /client.pem -t {Adoption token} \
  rtsp \
  -s {rtsp stream}
```

### Hardware Acceleration

```
unifi-cam-proxy -H {NVR IP} -i {Camera IP} -c /client.pem -t {Adoption token} \
  rtsp \
  -s {rtsp stream} \
  --ffmpeg-args='-hwaccel vaapi -hwaccel_device /dev/dri/renderD128 -hwaccel_output_format yuv420p'
```
