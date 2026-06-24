#!/bin/bash
# One-time setup: create UnlockMac Shortcut
# This opens Shortcuts app and auto-creates the shortcut via GUI automation

set -e

cat << 'GUIDE'

╔══════════════════════════════════════════════╗
║       创建 UnlockMac Shortcut (一次性)        ║
╠══════════════════════════════════════════════╣
║  Shortcuts app 将打开并自动创建快捷指令        ║
║  如果自动创建失败, 请手动按照指引操作          ║
╚══════════════════════════════════════════════╝

GUIDE

# AppleScript to create shortcut
osascript -e '
tell application "Shortcuts"
    activate
end tell

delay 2

tell application "System Events"
    tell process "Shortcuts"
        -- Cmd+N = new shortcut
        keystroke "n" using {command down}
        delay 1
        
        -- Type name
        keystroke "UnlockMac"
        delay 0.5
        key code 36  -- Return
        delay 1
        
        -- Cmd+F = search actions
        keystroke "f" using {command down}
        delay 0.5
        
        -- Search "Run AppleScript"
        keystroke "Run AppleScript"
        delay 1
        key code 36  -- Return to select action
        delay 1
    end tell
end tell
' 2>/dev/null

echo ""
echo "如果 Shortcuts 窗口已打开, 请手动完成:"
echo "  1. 双击 'Run AppleScript' action 编辑脚本"
echo "  2. 粘贴 ~/mac-proximity-unlock/unlock_script.applescript 的内容"
echo "  3. Cmd+S 保存"
echo ""
echo "完成后运行 python3 main.py"
