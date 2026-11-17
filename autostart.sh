#!/bin/bash
# 로그인하면 자비스가 켜지고, 꺼지면 다시 켜지게 (macOS launchd = 4편의 "관리자" 역할)
#   ./autostart.sh on   등록    ·   ./autostart.sh off   해제
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST="$HOME/Library/LaunchAgents/local.jarvis.plist"
if [ "$1" = "off" ]; then
  launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null || true
  rm -f "$PLIST"; echo "자동 실행 해제"; exit
fi
CLAUDE_DIR="$(dirname "$(command -v claude)")"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>local.jarvis</string>
  <key>ProgramArguments</key><array>
    <string>$DIR/.venv/bin/python</string><string>$DIR/jarvis.py</string><string>--no-face</string>
  </array>
  <key>WorkingDirectory</key><string>$DIR</string>
  <key>EnvironmentVariables</key><dict>
    <key>PATH</key><string>$CLAUDE_DIR:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>5</integer>
  <key>StandardOutPath</key><string>$DIR/jarvis.log</string>
  <key>StandardErrorPath</key><string>$DIR/jarvis.log</string>
</dict></plist>
EOF
launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "자동 실행 등록 — 로그: $DIR/jarvis.log"
echo "GROQ_API_KEY 를 쓰려면: launchctl setenv GROQ_API_KEY 키값  (파일에 적지 않음)"
