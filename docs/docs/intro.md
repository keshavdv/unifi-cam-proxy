---
slug: /
sidebar_position: 1
---

# Installation

## Prerequisites

### Certificate
Generate a certificate by performing one of the following:


1. If you have a UniFi camera: 
```
scp ubnt@<your-unifi-cam>:/var/etc/persistent/server.pem client.pem
```
2. Create your own client certificate via:
```
openssl ecparam -out /tmp/private.key -name prime256v1 -genkey -noout
openssl req -new -sha256 -key /tmp/private.key -out /tmp/server.csr -subj "/C=TW/L=Taipei/O=Ubiquiti Networks Inc./OU=devint/CN=camera.ubnt.dev/emailAddress=support@ubnt.com"
openssl x509 -req -sha256 -days 36500 -in /tmp/server.csr -signkey /tmp/private.key -out /tmp/public.key
cat /tmp/private.key /tmp/public.key > client.pem
rm -f /tmp/private.key /tmp/public.key /tmp/server.csr
```

### Adoption Token
In order to add a camera to Protect, you must first generate an adoption token. The token is only valid for 60 minutes so you'll need to re-generate a new one if it expires during your initial setup.

1. On the Protect UI, click 'Add Devices' and select 'G3 Micro'. Select 'Continue on Web' and type in a random string for the SSID and Password fields and click 'Generate QR Code'.
   * If you do not see this button, manually go to https://{NVR IP}/protect/devices/add (notice the "/devices/add")
   * Per a discussion post, try this URL: https://{NVR IP}/proxy/protect/api/cameras/qr
2. Take a screenshot of the QR code and upload it to https://zxing.org/w/decode.jspx
3. Decode the QR code and extract the token from the second to last line in the 'Raw Text' field.

## Docker
Using Docker is the recommended installation method. The sample docker-compose file below is the recommended deployment for most users. Note that the certificate generated in the previous step must be in the same directory as the docker-compose.yaml file.

```
version: "3.9"
services:
  unifi-cam-proxy:
    restart: unless-stopped
    image: keshavdv/unifi-cam-proxy
    volumes:
      - "./client.pem:/client.pem"
    command: unifi-cam-proxy --host {NVR IP} --cert /client.pem --token {Adoption token} rtsp -s rtsp://192.168.201.15:8554/cam'
```

### Multiple cameras
To use multiple cameras, start an instance of the proxy for each, with a unique MAC address argument. Using docker-compose, your setup might look like the following: 

*** Note: This conforms to MAC randomization rules, so should not cause issues with real devices. See here for more details: https://www.mist.com/get-to-know-mac-address-randomization-in-2020/ ***

```
version: "3.5"
services:
  proxy-1:
    restart: unless-stopped
    image: keshavdv/unifi-cam-proxy
    volumes:
      - "./client.pem:/client.pem"
    command: unifi-cam-proxy --host {NVR IP} --mac 'AA:BB:CC:00:11:22' --cert /client.pem --token {Adoption token} rtsp -s rtsp://192.168.201.15:8554/cam'
  proxy-2:
    restart: unless-stopped
    image: keshavdv/unifi-cam-proxy
    volumes:
      - "./client.pem:/client.pem"
    command: unifi-cam-proxy --host {NVR IP} --mac 'AA:BB:CC:33:44:55' --cert /client.pem --token {Adoption token} rtsp -s rtsp://192.168.201.15:8554/cam'
```



## Bare Metal
If you cannot use Docker, you may install the proxy on most Linux distros, but support is not guaranteed. Find instructions for your distro below:

### Ubuntu/Debian
```
apt install ffmpeg netcat python3 python3-pip
pip3 install unifi-cam-proxy
unifi-cam-proxy --host {NVR IP} --cert /client.pem --token {Adoption token} rtsp -s rtsp://192.168.201.15:8554/cam'
```
