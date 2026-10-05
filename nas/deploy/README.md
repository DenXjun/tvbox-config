# Synology x86_64 deployment

This directory is the small deployment entry point. Do not upload the full repository.

1. Copy Dockerfile and docker-compose.yml to one NAS folder.
2. Create data, output, config and logs subdirectories.
3. In Container Manager create a Project from that folder.
4. Build and start.
5. Open http://NAS-IP:8787/
6. Click the maintenance button. The final VOD subscription is http://NAS-IP:8787/tvbox.json

The image uses Git sparse checkout during build and deliberately excludes the >1GB historical deps cache.
Pinned source commit: 9c03e3fe5edc98fba57db4b25678f0316fd96d7f
