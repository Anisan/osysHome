#!/bin/sh
set -e

cd /app

mkdir -p logs cache files/public files/private files/secure plugins

if [ ! -s /app/config.yaml ]; then
  echo "[entrypoint] Creating config.yaml from sample_config.yaml"
  cp /app/sample_config.yaml /app/config.yaml
fi

if [ -z "$(ls -A /app/plugins 2>/dev/null)" ]; then
  echo "[entrypoint] plugins/ is empty, installing recommended plugins"
  /app/docker/install-recommended-plugins.sh /app/plugins
fi

exec "$@"
