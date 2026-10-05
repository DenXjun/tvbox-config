FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends nodejs ca-certificates curl && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY . /app
ENV PYTHONUNBUFFERED=1 TVBOX_DATA=/data TVBOX_OUTPUT=/output TVBOX_CONFIG=/config TVBOX_LOGS=/logs TVBOX_PORT=8080
EXPOSE 8080
VOLUME ["/data","/output","/config","/logs"]
CMD ["python","nas/app.py"]
