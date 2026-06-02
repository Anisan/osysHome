#!/bin/sh
set -e

REPO_BASE="https://github.com/Anisan"
PLUGINS_DIR="${1:-/app/plugins}"

echo "[osysHome] Installing recommended plugins into ${PLUGINS_DIR}"

mkdir -p "${PLUGINS_DIR}"

clone_if_missing() {
  repo_name="$1"
  target_dir="$2"
  dest="${PLUGINS_DIR}/${target_dir}"

  if [ -d "${dest}" ]; then
    echo "  - ${dest} already exists, skipping"
    return
  fi

  echo "  - Cloning ${repo_name} into ${dest}"
  git clone --depth 1 "${REPO_BASE}/${repo_name}.git" "${dest}"
}

clone_if_missing "osysHome-Modules" "Modules"
clone_if_missing "osysHome-Objects" "Objects"
clone_if_missing "osysHome-Users" "Users"
clone_if_missing "osysHome-Scheduler" "Scheduler"
clone_if_missing "osysHome-wsServer" "wsServer"
clone_if_missing "osysHome-Dashboard" "Dashboard"

echo "[osysHome] Recommended plugins installation completed."
