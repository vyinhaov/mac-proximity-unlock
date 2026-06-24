#!/usr/bin/env python3
"""诊断: 测试各键盘注入方式在锁屏界面能否正常工作
用法: python3 scripts/diag_unlock.py
请先手动锁屏，然后运行此脚本。它会尝试不同的方式输入测试文本。
"""
import subprocess, time, ctypes, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

TEST_TEXT = "hello"

def check_locked():
    """检查当前是否锁屏"""
    from actions.unlocker import is_screen_locked
    return is_screen_locked()

def method_1_cgevent_keycode():
    """CGEventPost kCGHIDEventTap + 物理 keycode (非 unicode 注入)"""
    import Quartz as Q

    # keycode 映射 (US)
    kc_map = {
        'h': 4, 'e': 14, 'l': 37, 'o': 31, ' ': 49,
    }

    print("  [CGEventPost keycode] 发送按键...", flush=True)
    for ch in TEST_TEXT:
        kc = kc_map.get(ch, 0)
        if kc == 0:
            continue
        # keyDown
        ev = Q.CGEventCreateKeyboardEvent(None, kc, True)
        Q.CGEventPost(Q.kCGHIDEventTap, ev)
        time.sleep(0.01)
        # keyUp
        ev = Q.CGEventCreateKeyboardEvent(None, kc, False)
        Q.CGEventPost(Q.kCGHIDEventTap, ev)
        time.sleep(0.05)
    time.sleep(0.3)
    print("  [CGEventPost keycode] done", flush=True)

def method_2_cgspost():
    """CGSPostKeyboardEvent"""
    from actions.unlocker import _cgs_key, _conn
    # keycode 映射
    kc_map = {'h': 4, 'e': 14, 'l': 37, 'o': 31}
    conn = _conn()
    print(f"  [CGSPostKeyboardEvent] conn={conn}, 发送按键...", flush=True)
    for ch in TEST_TEXT:
        kc = kc_map.get(ch, 0)
        if kc == 0:
            continue
        _cgs_key(kc, True)
        _cgs_key(kc, False)
        time.sleep(0.05)
    time.sleep(0.3)
    print("  [CGSPostKeyboardEvent] done", flush=True)

def method_3_osascript():
    """osascript System Events keystroke"""
    script = f'tell application "System Events" to keystroke "{TEST_TEXT}"'
    print(f"  [osascript] 执行...", flush=True)
    r = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True, text=True, timeout=10,
    )
    print(f"  [osascript] rc={r.returncode} stderr={r.stderr[:100]}", flush=True)

def method_4_cgevent_unicode():
    """CGEventPost + unicode 注入 (旧方案)"""
    import Quartz as Q
    print("  [CGEventPost unicode] 发送按键...", flush=True)
    for ch in TEST_TEXT:
        ev = Q.CGEventCreateKeyboardEvent(None, 0, True)
        Q.CGEventKeyboardSetUnicodeString(ev, 1, ch)
        Q.CGEventPost(Q.kCGHIDEventTap, ev)
        time.sleep(0.03)
    time.sleep(0.3)
    print("  [CGEventPost unicode] done", flush=True)

def main():
    print("=" * 60)
    print("键盘注入诊断")
    print("=" * 60)

    locked = check_locked()
    print(f"\n当前锁屏状态: {'LOCKED' if locked else 'UNLOCKED'}")

    if not locked:
        print("\n⚠️  屏幕未锁定。请手动锁屏后重新运行。")
        print("   (Ctrl+Cmd+Q 或触发远程锁屏)")
        return

    print(f"\n将依次尝试 4 种方式输入 '{TEST_TEXT}'")
    print("请在 Mac 解锁界面观察是否有字符出现。\n")

    methods = [
        ("CGEventPost + keycode (keyDown/Up)", method_1_cgevent_keycode),
        ("CGSPostKeyboardEvent", method_2_cgspost),
        ("osascript keystroke", method_3_osascript),
        ("CGEventPost + unicode 注入 (旧)", method_4_cgevent_unicode),
    ]

    results = []
    for name, func in methods:
        print(f"\n--- {name} ---")
        try:
            func()
            results.append((name, "OK (无异常)"))
        except Exception as e:
            results.append((name, f"ERROR: {e}"))
        time.sleep(2.0)  # 方法间隔

    print("\n" + "=" * 60)
    print("诊断结果:")
    for name, result in results:
        print(f"  {name}: {result}")
    print("\n请观察锁屏界面, 看哪种方式实际出现了 'hello' 字符。")
    print("=" * 60)

if __name__ == "__main__":
    main()
