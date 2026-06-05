#!/usr/bin/env bash
set -euo pipefail

LABEL="com.anton.elliott-wave.daily-report"
DST="${HOME}/Library/LaunchAgents/${LABEL}.plist"

if [ -f "${DST}" ]; then
  launchctl unload "${DST}" 2>/dev/null || true
  rm "${DST}"
fi

echo "Uninstalled ${LABEL}"
