ARG BUILD_FROM=ghcr.io/home-assistant/base:latest
FROM $BUILD_FROM

RUN apk add --no-cache python3

WORKDIR /app
COPY server.py /app/server.py
COPY www /app/www
COPY run.sh /run.sh
RUN chmod a+x /run.sh

CMD ["/run.sh"]
