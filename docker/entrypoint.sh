#!/bin/sh

if [ ! -z "${RTSP_URL:-}" ] && [ ! -z "${HOST}" ] && [ ! -z "${TOKEN}" ]; then
  echo "Using RTSP streom from $RTSP_URL"
  exec unifi-cam-proxy --host "$HOST" --name "${NAME:-unifi-cam-proxy}" --mac "${MAC:-'AA:BB:CC:00:11:22'}" --cert /config/client.pem --token "$TOKEN" rtsp -s "$RTSP_URL"
fi

exec "$@"
