#!/usr/bin/env bash
set -euo pipefail

cd "/Users/DEV/Elliott-wave"

LABEL="com.anton.elliott-wave.daily-report"
SRC="scripts/${LABEL}.plist"
DST="${HOME}/Library/LaunchAgents/${LABEL}.plist"

chmod +x "scripts/run_daily_report.sh"
mkdir -p "${HOME}/Library/LaunchAgents"
mkdir -p "brain-output/signals/logs"

if launchctl list | grep -q "${LABEL}"; then
  launchctl unload "${DST}" 2>/dev/null || true
fi

cp "${SRC}" "${DST}"
launchctl load "${DST}"

echo "Installed ${LABEL}"
launchctl list | grep "${LABEL}" || true
