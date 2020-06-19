FROM python:2.7
RUN pip install unifi-cam-proxy
ENTRYPOINT ["unifi-cam-proxy"]
