#!/bin/sh
# Baut die drei WEISS-Images direkt aus dem Upstream-Git-Repo (rootless).
# Nutzung: scripts/build-images.sh [env-datei]   (Standard: ~/.config/weiss/weiss.env)
# Version wählen: WEISS_REF=v1.2.3 scripts/build-images.sh
set -eu

ENV_FILE="${1:-$HOME/.config/weiss/weiss.env}"
REF="${WEISS_REF:-main}"
REPO="https://github.com/weiss-controls/weiss.git#$REF"

if [ -f "$ENV_FILE" ]; then
    set -a
    . "$ENV_FILE"
    set +a
fi

# Die VITE_*-Werte werden beim Frontend-Build fest eingebacken.
podman build --target prod \
    --build-arg "VITE_DEMO_MODE=${DEMO_MODE:-false}" \
    --build-arg "VITE_AUTH_IDENTITY_PROVIDER=${AUTH_IDENTITY_PROVIDER:-oauth}" \
    -t localhost/weiss:latest "$REPO"
podman build -t localhost/weiss-epicsws:latest "$REPO:backend/epicsWS"
podman build -t localhost/weiss-api:latest "$REPO:backend/api"
