---
sidebar_position: 3
---

# Hikvision

### Generic
If your camera model is not listed specifically below, try the following:

```
unifi-cam-proxy -H <NVR IP> -i <camera IP> -c client.pem -t <Adoption token> hikvision -u <username> -p <password>
```

### Options
```
optional arguments:
  --ffmpeg-args FFMPEG_ARGS, -f FFMPEG_ARGS
                        Transcoding args for `ffmpeg -i <src> <args> <dst>`
  --rtsp-transport {tcp,udp,http,udp_multicast}
                        RTSP transport protocol used by stream
  --username USERNAME, -u USERNAME
                        Camera username
  --password PASSWORD, -p PASSWORD
                        Camera password
```


### Hikvision DS-2DE3304W-DE
- [x] Supports full time recording
- [ ] Supports motion events
- [ ] Supports smart detection
- Notes:
  * Change Pan/Tilt/Zoom via brightness/saturation/hue camera setting
```
unifi-cam-proxy -H <NVR IP> -i <camera IP> -c client.pem -t <Adoption token> hikvision -u <username> -p <password>
```
