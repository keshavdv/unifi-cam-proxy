FROM python:3.7
RUN apt-get -y update && apt-get install -y \
  ffmpeg \
  netcat-openbsd
RUN pip install unifi-cam-proxy
COPY ./entrypoint.sh /
ENTRYPOINT ["/entrypoint.sh"]
CMD ["unifi-cam-proxy"]
