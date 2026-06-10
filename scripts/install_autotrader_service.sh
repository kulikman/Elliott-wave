#!/usr/bin/env bash
# Устанавливает авто-трейдер как macOS LaunchAgent (запуск при логине, авто-рестарт)
set -euo pipefail

PLIST_SRC="$(dirname "$0")/com.ewb.autotrader.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.ewb.autotrader.plist"

cp "$PLIST_SRC" "$PLIST_DST"
launchctl unload "$PLIST_DST" 2>/dev/null || true
launchctl load -w "$PLIST_DST"

echo "✓ Сервис установлен и запущен"
echo "  Статус: launchctl list | grep ewb"
echo "  Стоп:   launchctl unload ~/Library/LaunchAgents/com.ewb.autotrader.plist"
echo "  Лог:    tail -f /Users/DEV/Elliott-wave/brain-output/auto_trader.log"
