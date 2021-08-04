FROM python:3.7
WORKDIR /app

RUN apt-get -y update && apt-get install -y \
  ffmpeg \
  netcat-openbsd

COPY . .

RUN pip install .

COPY ./docker/entrypoint.sh /

ENTRYPOINT ["/entrypoint.sh"]
CMD ["unifi-cam-proxy"]
