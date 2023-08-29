ARG VARIANT="3.9"
FROM mcr.microsoft.com/vscode/devcontainers/python:dev-${VARIANT}-buster
WORKDIR /app

RUN apt-get update && apt-get install -y ffmpeg netcat-openbsd

COPY . .
RUN pip install .