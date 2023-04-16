ARG version=3.9
ARG tag=${version}-alpine3.17

FROM python:${tag} as builder
WORKDIR /app

RUN apk add --update gcc g++ musl-dev rust cargo patchelf libc-dev linux-headers zlib-dev jpeg-dev

RUN pip install -U pip wheel setuptools maturin
COPY requirements.txt .
RUN pip install -r requirements.txt --no-build-isolation


FROM python:${tag}
WORKDIR /app

ARG version

COPY --from=builder /usr/local/lib/python${version}/site-packages /usr/local/lib/python${version}/site-packages
RUN apk add --update ffmpeg netcat-openbsd libusb-dev

COPY . .
RUN pip install . --no-cache-dir

COPY ./docker/entrypoint.sh /

ENTRYPOINT ["/entrypoint.sh"]
CMD ["unifi-cam-proxy"]
