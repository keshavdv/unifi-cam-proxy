---
sidebar_position: 2
---

# Frigate


If your camera model is not listed specifically below, try the following:

- [x] Supports full time recording
- [ ] Supports motion events
- [x] Supports smart detection


```
unifi-cam-proxy -H <NVR IP> -i <camera IP> -c client.pem -t <Adoption token> \
  frigate \
  -s <rtsp source> \
  --mqtt-host <mqtt host> \
  --frigate-camera <Name of camera in frigate>
```

## Options

```
optional arguments:
  --ffmpeg-args FFMPEG_ARGS, -f FFMPEG_ARGS
                        Transcoding args for `ffmpeg -i <src> <args> <dst>`
  --rtsp-transport {tcp,udp,http,udp_multicast}
                        RTSP transport protocol used by stream
  --source SOURCE, -s SOURCE
                        Stream source
  --http-api HTTP_API   Specify a port number to enable the HTTP API (default: disabled)
  --snapshot-url SNAPSHOT_URL, -i SNAPSHOT_URL
                        HTTP endpoint to fetch snapshot image from
  --mqtt-host MQTT_HOST
                        MQTT server
  --mqtt-port MQTT_PORT
                        MQTT server
  --mqtt-prefix MQTT_PREFIX
                        Topic prefix
  --frigate-camera FRIGATE_CAMERA
                        Name of camera in frigate
```

