#!/bin/sh
set -eu

if [ "$#" -eq 0 ]; then
  set -- serve-http
fi

if [ "$1" = "serve-stdio" ] || [ "$1" = "serve-http" ]; then
  mkdir -p "${ARTIFACTS_DIR:-/tmp/nutanix-mcp-artifacts}" "${LOG_DIR:-/tmp/nutanix-mcp-logs}"

  if ! find "${ARTIFACTS_DIR:-/tmp/nutanix-mcp-artifacts}" -maxdepth 1 -type f -name '*-all-documentation.yaml' | grep -q .; then
    echo "No Nutanix API artifacts found; bootstrapping before $1." >&2
    python -m src.container_bootstrap >&2
  fi
fi

exec nutanix-mcp "$@"
