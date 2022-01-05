---
sidebar_position: 4
---

# Reolink

### Generic
If your camera model is not listed specifically below, try the following:

```
unifi-cam-proxy -H <NVR IP> -i <camera IP> -c client.pem -t <Adoption token> rtsp -s <rtsp stream> --ffmpeg-args '-c:v copy -vbsf "h264_metadata=tick_rate=60000/1001:fixed_frame_rate_flag=1" -ar 32000 -ac 2 -codec:a aac -b:a 32k'

```

### NVR (Reolink RLN16-410)
- [x] Supports full time recording
- [x] Supports motion events
- [ ] Supports smart detection
- Notes:
  *  Camera/channel IDs are zero-based
```
unifi-cam-proxy -H {Protect IP} -i {Reolink NVR IP} -c client.pem -t {Adoption token} reolink_nvr -u {username} -p {password} -c {Camera channel}
```

#### Options
```
optional arguments:
  -h, --help            show this help message and exit
  --ffmpeg-args FFMPEG_ARGS, -f FFMPEG_ARGS
                        Transcoding args for `ffmpeg -i <src> <args> <dst>`
  --rtsp-transport {tcp,udp,http,udp_multicast}
                        RTSP transport protocol used by stream
  --username USERNAME, -u USERNAME
                        NVR username
  --password PASSWORD, -p PASSWORD
                        NVR password
  --channel CHANNEL, -c CHANNEL
                        NVR camera channel
```                        




### RLC-410-5MP
- [x] Supports full time recording
- [ ] Supports motion events
- [ ] Supports smart detection
 
```
unifi-cam-proxy -H <NVR IP> -i <camera IP> -c client.pem -t <Adoption token> rtsp -s <rtsp stream> --ffmpeg-args '-c:v copy -vbsf "h264_metadata=tick_rate=60000/1001" -ar 32000 -ac 1 -codec:a aac -b:a 32k'
```
