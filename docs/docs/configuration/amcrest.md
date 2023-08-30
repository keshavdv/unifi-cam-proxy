---
sidebar_position: 3
---

# Amcrest

## Options

```text
optional arguments:
  --ffmpeg-args FFMPEG_ARGS, -f FFMPEG_ARGS
                        Transcoding args for `ffmpeg -i <src> <args> <dst>`
  --rtsp-transport {tcp,udp,http,udp_multicast}
                        RTSP transport protocol used by stream
  --username USERNAME, -u USERNAME
                        Camera username
  --password PASSWORD, -p PASSWORD
                        Camera password
  --channel CHANNEL, -c CHANNEL
                        Camera channel
  --snapshot-channel SNAPSHOT_CHANNEL
                        Snapshot channel
  --main-stream MAIN_STREAM
                        Main Stream subtype index
  --sub-stream SUB_STREAM
                        Sub Stream subtype index
  --motion-index MOTION_INDEX
                        VideoMotion event index
```

## Amcrest IP8M-T2599E

- [x] Supports full time recording
- [x] Supports motion events
- [ ] Supports smart detection
- Notes:
  - Camera configuration:
    - Video codec must be H.264 (H.265/HEVC is not supported).
    - Audio codec should be AAC. If not, adjust the ffmpeg args to re-encode to AAC.
    - Ensure the sub stream is enabled.
    - If desired, ensure motion detection is enabled with the desired anti-dither and detection area.
  - The `-bsf:v` parameter is needed to make live video work.
    The first `tick_rate` value should be `fps * 2000`.
    See [this comment](https://github.com/keshavdv/unifi-cam-proxy/issues/31#issuecomment-841914363).

```sh
unifi-cam-proxy --mac '{unique MAC}' -H {NVR IP} -i {camera IP} -c /client.pem -t {Adoption token} \
    amcrest \
    -u {username} \
    -p {password} \
    --motion-index 0 \
    --snapshot-channel 1 \
    --ffmpeg-args='-c:a copy -c:v copy -bsf:v "h264_metadata=tick_rate=30000/1001"'
```
