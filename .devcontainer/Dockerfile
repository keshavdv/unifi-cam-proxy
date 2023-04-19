ARG VARIANT="3.9"
FROM mcr.microsoft.com/vscode/devcontainers/universal
WORKDIR /app

RUN apt-get update && apt-get install -y ffmpeg netcat-openbsd

COPY . .
RUN pip install .