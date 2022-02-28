---
sidebar_position: 4
---

# Reolink

### Generic
If your camera model is not listed specifically below, try the following:

```
unifi-cam-proxy -H <NVR IP> -i <camera IP> -c client.pem -t <Adoption token> \
    reolink \
    -u {username} \
    -p {password} \
    -s "main" \
    --ffmpeg-args='-c:v copy -bsf:v "h264_metadata=tick_rate=60000/1001" -ar 32000 -ac 1 -codec:a aac -b:a 32k'
```

### Options
```
optional arguments:
  -h, --help            show this help message and exit
  --ffmpeg-args FFMPEG_ARGS, -f FFMPEG_ARGS
                        Transcoding args for `ffmpeg -i <src> <args> <dst>`
  --rtsp-transport {tcp,udp,http,udp_multicast}
                        RTSP transport protocol used by stream
  --username USERNAME, -u USERNAME
                        Camera username
  --password PASSWORD, -p PASSWORD
                        Camera password
  --substream SUBSTREAM, -s CHANNEL
                        Camera rtsp url substream index main, or sub
```        

### RLC-410-5MP
- [x] Supports full time recording
- [x] Supports motion events
- [ ] Supports smart detection
- Notes:
  *  When using the 'sub' substream, use `tick_rate=30000/1001` because the stream is limited to a maximum of 15fps

```
unifi-cam-proxy -H <NVR IP> -i <camera IP> -c client.pem -t <Adoption token> \
    reolink \
    -u {username} \
    -p {password} \
    -s "main" \
    --ffmpeg-args='-c:v copy -bsf:v "h264_metadata=tick_rate=60000/1001" -ar 32000 -ac 1 -codec:a aac -b:a 32k'
```
