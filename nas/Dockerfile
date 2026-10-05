FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends nodejs ca-certificates curl && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY runtime.tar.gz /tmp/runtime.tar.gz
RUN tar -xzf /tmp/runtime.tar.gz -C /app && rm /tmp/runtime.tar.gz
ENV PYTHONUNBUFFERED=1 TVBOX_DATA=/data TVBOX_OUTPUT=/output TVBOX_CONFIG=/config TVBOX_LOGS=/logs TVBOX_PORT=8080 LIVE_SPEEDTEST=0
EXPOSE 8080
VOLUME ["/data","/output","/config","/logs"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD curl -fsS http://127.0.0.1:8080/api/status || exit 1
CMD ["python","nas/app.py"]
