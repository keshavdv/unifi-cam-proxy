# syntax=docker/dockerfile:1.2
FROM python:3.9-alpine as build
WORKDIR /build
# any dependencies in python which requires a compiled c/c++ code (if any)
RUN apk add --update gcc libc-dev linux-headers libusb-dev
RUN --mount=target=. \
    pip3 install --prefix=/srv/unifi-cam-proxy . && find /srv/unifi-cam-proxy

FROM python:3.9-alpine
WORKDIR /srv/unifi-cam-proxy
ENV PYTHONPATH="/srv/unifi-cam-proxy/lib/python3.9/site-packages"
ENV PATH="$PATH:/srv/unifi-cam-proxy/bin"

RUN apk add --update ffmpeg netcat-openbsd
COPY --from=build /srv/unifi-cam-proxy .
COPY ./docker/entrypoint.sh /

ENTRYPOINT ["/entrypoint.sh"]
CMD ["unifi-cam-proxy"]
