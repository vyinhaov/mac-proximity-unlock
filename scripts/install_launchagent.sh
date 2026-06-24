#!/bin/bash
# ============================================================
# 安装 LaunchAgent 开机自启
# ============================================================
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
PLIST_FILE="$LAUNCH_AGENTS_DIR/com.proximity-unlock.plist"
LOG_DIR="$HOME/Library/Logs/mac-auto-unlock"

mkdir -p "$LAUNCH_AGENTS_DIR"
mkdir -p "$LOG_DIR"

echo "=== 安装 Proximity Unlock LaunchAgent ==="
echo "项目路径: $PROJECT_DIR"
echo ""

cat > "$PLIST_FILE" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.proximity-unlock</string>

    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>${PROJECT_DIR}/main.py</string>
    </array>

    <key>WorkingDirectory</key>
    <string>${PROJECT_DIR}</string>

    <key>StandardOutPath</key>
    <string>${LOG_DIR}/stdout.log</string>

    <key>StandardErrorPath</key>
    <string>${LOG_DIR}/stderr.log</string>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <true/>

    <key>ThrottleInterval</key>
    <integer>10</integer>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PYTHONPATH</key>
        <string>${PROJECT_DIR}</string>
    </dict>
</dict>
</plist>
EOF

echo "✅ Plist 已创建: $PLIST_FILE"

# 加载
launchctl load "$PLIST_FILE" 2>/dev/null && echo "✅ LaunchAgent 已加载" || {
    echo "⚠️  加载失败，尝试卸载后重新加载..."
    launchctl unload "$PLIST_FILE" 2>/dev/null || true
    launchctl load "$PLIST_FILE" && echo "✅ LaunchAgent 已加载" || echo "❌ 加载失败"
}

echo ""
echo "检查状态:"
launchctl list com.proximity-unlock 2>/dev/null && echo "  🔄 运行中" || echo "  ⏸️  未运行"

echo ""
echo "日志文件:"
echo "  stdout: $LOG_DIR/stdout.log"
echo "  stderr: $LOG_DIR/stderr.log"
echo ""
echo "管理命令:"
echo "  启动: launchctl load $PLIST_FILE"
echo "  停止: launchctl unload $PLIST_FILE"
echo "  状态: launchctl list com.proximity-unlock"
echo ""
