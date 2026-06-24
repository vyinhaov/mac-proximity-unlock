#!/bin/bash
# ============================================================
# mac-proximity-unlock 初始化脚本
# 功能: 引导用户将 Mac 登录密码存入 Keychain
# ============================================================
set -euo pipefail

SERVICE="MacAutoUnlock"
ACCOUNT="local_mac"

echo "=== Mac 近距解锁 - 初始化 ==="
echo ""
echo "本工具需要在 Keychain 中存储你的 Mac 登录密码，用于自动解锁。"
echo "密码仅存储在本机 Keychain（加密存储），不会被传输到远程。"
echo ""

# 检查是否已有密码
EXISTING=$(security find-generic-password -s "$SERVICE" -a "$ACCOUNT" -w 2>/dev/null || echo "")
if [ -n "$EXISTING" ]; then
    echo "⚠️  Keychain 中已存在密码。"
    read -p "是否覆盖？(y/N): " OVERWRITE
    if [ "$OVERWRITE" != "y" ] && [ "$OVERWRITE" != "Y" ]; then
        echo "已保留现有密码。"
        exit 0
    fi
fi

# 读取密码（隐藏输入）
echo ""
echo "请输入你的 Mac 登录密码（输入时不会显示）:"
read -s PASSWORD
echo ""

if [ -z "$PASSWORD" ]; then
    echo "❌ 密码不能为空"
    exit 1
fi

read -p "再次输入确认: " -s PASSWORD2
echo ""

if [ "$PASSWORD" != "$PASSWORD2" ]; then
    echo "❌ 两次输入不一致"
    exit 1
fi

# 更新 Keychain
security delete-generic-password -s "$SERVICE" -a "$ACCOUNT" 2>/dev/null || true
security add-generic-password -s "$SERVICE" -a "$ACCOUNT" -w "$PASSWORD" -U

echo ""
echo "✅ 密码已安全存储在 Keychain 中"
echo ""
echo "后续步骤:"
echo "  1. 授予 Accessibility 权限:"
echo "     系统设置 → 隐私与安全性 → 辅助功能 → 添加"
echo "     /usr/bin/python3 和 /usr/bin/osascript"
echo "  2. 配置 SSH 免密登录远程 Mac:"
echo "     ssh-copy-id your_ssh_user@x.x.x.x"
echo "  3. 安装 LaunchAgent 开机自启:"
echo "     bash scripts/install_launchagent.sh"
echo "  4. 启动服务:"
echo "     python3 main.py"
echo ""
