ARG BUILD_FROM=ghcr.io/home-assistant/base:latest
FROM $BUILD_FROM

RUN apk add --no-cache python3 py3-pip py3-cryptography \
  && (pip3 install --no-cache-dir --break-system-packages pywebpush || pip3 install --no-cache-dir pywebpush)

WORKDIR /app
COPY server.py /app/server.py
COPY run.sh /run.sh
RUN chmod a+x /run.sh

CMD ["/run.sh"]
