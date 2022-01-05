FROM python:3.8-alpine3.10
WORKDIR /app

RUN apk add --update gcc libc-dev linux-headers libusb-dev
RUN apk add --update ffmpeg=4.1.6-r0 netcat-openbsd

COPY . .
RUN pip install .

COPY ./docker/entrypoint.sh /

ENTRYPOINT ["/entrypoint.sh"]
CMD ["unifi-cam-proxy"]
