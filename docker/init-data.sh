#!/usr/bin/env bash
set -e

OSYSHOME_RAW_BASE="${OSYSHOME_RAW_BASE:-https://raw.githubusercontent.com/Anisan/osysHome/master}"

resolve_root_dir() {
  local script_path="${BASH_SOURCE[0]:-$0}"

  if [ -f "$script_path" ]; then
    local script_dir
    script_dir="$(cd "$(dirname "$script_path")" && pwd)"
    if [ "$(basename "$script_dir")" = "docker" ]; then
      dirname "$script_dir"
    else
      echo "$script_dir"
    fi
  else
    pwd
  fi
}

fetch_if_missing() {
  local file="$1"
  local url="$2"

  if [ ! -f "$file" ]; then
    echo "[init-data] Downloading ${file}..."
    curl -fsSL "$url" -o "$file"
  fi
}

ROOT_DIR="$(resolve_root_dir)"
cd "$ROOT_DIR"

mkdir -p logs cache files/public files/private files/secure plugins

fetch_if_missing "sample_config.yaml" "${OSYSHOME_RAW_BASE}/sample_config.yaml"
fetch_if_missing "docker-compose.yml" "${OSYSHOME_RAW_BASE}/docker-compose.yml"

if [ ! -f config.yaml ]; then
  cp sample_config.yaml config.yaml
  echo "[init-data] Created config.yaml from sample_config.yaml"
fi

if [ ! -e app.db ]; then
  touch app.db
  echo "[init-data] Created empty app.db (SQLite will initialize on first start)"
fi

echo "[init-data] Data directories are ready in: ${ROOT_DIR}"
echo "[init-data] Next: edit config.yaml, then run: docker compose up -d"
