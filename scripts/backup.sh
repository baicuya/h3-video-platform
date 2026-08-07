#!/usr/bin/env bash
set -euo pipefail
BACKUP_ROOT=/home/ubuntu/backups/h3-video-platform
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
DEST="$BACKUP_ROOT/$STAMP"
mkdir -p "$DEST"
pg_dump --format=custom --file="$DEST/database.dump" h3_video_platform
tar --create --gzip --file="$DEST/project-config.tar.gz" --exclude=node_modules --exclude=.next --exclude=.venv -C /home/ubuntu/workspace h3-video-platform
tar --create --gzip --file="$DEST/media.tar.gz" -C /home/ubuntu data
echo "$DEST"

