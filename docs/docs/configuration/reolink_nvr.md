---
sidebar_position: 5
---

# Reolink NVR

## Options

```text
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

## NVR (Reolink RLN16-410)

- [x] Supports full time recording
- [x] Supports motion events
- [ ] Supports smart detection
- Notes:
  - Camera/channel IDs are zero-based

```sh
unifi-cam-proxy --mac '{unique MAC}' -H {Protect IP} -i {Reolink NVR IP} -c /client.pem -t {Adoption token} \
    reolink_nvr \
    -u {username} \
    -p {password} \
    -c {Camera channel}
```
