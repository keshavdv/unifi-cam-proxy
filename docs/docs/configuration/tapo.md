---
sidebar_position: 1
---

# Tapo
Unifi-cam-proxy has basic support for Tapo/TPlink cameras, like the C100 or C200 with PTZ. 

To control the PTZ functionality, you have to use the camera image settings in unifi. Adjusting the contrast to anything less than 20 pans the camera a bit to the left, anything over 80 to the right. The brightness setting controls the tilt.

Make sure to reset the brightness/contrast setting back to somewhere around 50 after adjusting the cameras position, to avoid adjusting the position by accident.

## Standard
```sh
unifi-cam-proxy -H {NVR IP} -i {Camera IP} -c /client.pem -t {Adoption token} --mac 'AA:BB:CC:00:11:22'\
  tapo \
  --rtsp "rtsp://{camera_username}:{camera_password}@{camera_ip}:554"
```

## PTZ Support
```sh
unifi-cam-proxy -H {NVR IP} -i {Camera IP} -c /client.pem -t {Adoption token} --mac 'AA:BB:CC:00:11:22'\
  tapo \
  --rtsp "rtsp://{camera_username}:{camera_password}@{camera_ip}:554"\
  --password "{TP Link account Password}"
```