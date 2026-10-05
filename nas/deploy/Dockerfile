FROM python:3.12-slim
ARG TVBOX_REF=9c03e3fe5edc98fba57db4b25678f0316fd96d7f
RUN apt-get update && apt-get install -y --no-install-recommends git nodejs npm ca-certificates curl && rm -rf /var/lib/apt/lists/*
WORKDIR /app
RUN git clone --filter=blob:none --no-checkout https://github.com/DenXjun/tvbox-config.git /tmp/src \
 && cd /tmp/src \
 && git sparse-checkout init --no-cone \
 && printf '%s\n' '/scripts/*' '/config/*' '/drpy-sandbox/*' '/nas/*' '/state/*' '/probe/*' '/tvbox.json' '/tvbox_recommended.json' '/vod.json' '/short.json' '/list.json' '/status.json' '/checks.json' > .git/info/sparse-checkout \
 && git checkout "$TVBOX_REF" \
 && cp -a scripts config drpy-sandbox nas state probe /app/ \
 && for f in tvbox.json tvbox_recommended.json vod.json short.json list.json status.json checks.json; do [ ! -f "$f" ] || cp "$f" /app/; done \
 && rm -rf /tmp/src \
 && mkdir -p /app/deps /data /output /config /logs \
 && cd /app/drpy-sandbox && npm ci --omit=dev && npm cache clean --force
ENV PYTHONUNBUFFERED=1 TVBOX_DATA=/data TVBOX_OUTPUT=/output TVBOX_CONFIG=/config TVBOX_LOGS=/logs TVBOX_PORT=8080 LIVE_SPEEDTEST=0
EXPOSE 8080
VOLUME ["/data","/output","/config","/logs"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD curl -fsS http://127.0.0.1:8080/api/status || exit 1
CMD ["python","nas/app.py"]
