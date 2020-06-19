FROM python:2.7
RUN apt-get -y update && apt-get install -y \
  ffmpeg \
  netcat
RUN pip install unifi-cam-proxy
ENTRYPOINT ["unifi-cam-proxy"]
