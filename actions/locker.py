"""
锁屏执行器 — 不再依赖 is_screen_locked() 验证
macOS 26 上 CGSessionCopyCurrentDictionary 在锁屏过渡期间不可靠。
每个方法只信任自身执行结果。
"""
import ctypes
import glob
import logging
import os
import subprocess
import time
from typing import Optional, Tuple

from actions.cgs_keyboard import lock_screen_cgs

logger = logging.getLogger("locker")

_CGSESSION_PATH: Optional[str] = None


def _discover_cgsession() -> Optional[str]:
    global _CGSESSION_PATH
    if _CGSESSION_PATH is not None:
        return _CGSESSION_PATH or None
    known = [
        "/System/Library/CoreServices/Menu Extras/User.menu/Contents/Resources/CGSession",
        "/System/Library/CoreServices/UserNotificationCenter.app/Contents/MacOS/CGSession",
    ]
    for p in known:
        if os.path.isfile(p) and os.access(p, os.X_OK):
            _CGSESSION_PATH = p; return p
    for pattern in ["/System/Library/CoreServices/**/CGSession"]:
        for p in glob.glob(pattern, recursive=True):
            if os.path.isfile(p) and os.access(p, os.X_OK):
                _CGSESSION_PATH = p; return p
    _CGSESSION_PATH = ""
    return None


def _try_shortcut() -> Tuple[bool, str]:
    """macOS LockScreen Shortcut"""
    try:
        r = subprocess.run(
            ["shortcuts", "run", "LockScreen"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0:
            return (True, "屏幕已锁定 (LockScreen Shortcut)")
        logger.debug(f"shortcuts rc={r.returncode}")
    except Exception as e:
        logger.debug(f"shortcuts 异常: {e}")
    return (False, "")


def _try_sse() -> Tuple[bool, str]:
    """ScreenSaverEngine — 仅当 askForPassword=1 时才视为有效锁屏"""
    try:
        r = subprocess.run(
            ["defaults", "-currentHost", "read", "com.apple.screensaver", "askForPassword"],
            capture_output=True, text=True, timeout=3,
        )
        if r.stdout.strip() != "1":
            return (False, "")
        r = subprocess.run(
            ["open", "-a", "/System/Library/CoreServices/ScreenSaverEngine.app"],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0:
            return (True, "屏幕已锁定 (ScreenSaverEngine)")
    except Exception as e:
        logger.debug(f"SSE: {e}")
    return (False, "")


def _try_cgs_keyboard() -> Tuple[bool, str]:
    """CGSPostKeyboardEvent Cmd+Ctrl+Q — WindowServer 级别"""
    try:
        if lock_screen_cgs():
            return (True, "屏幕已锁定 (CGSPostKeyboardEvent Cmd+Ctrl+Q)")
    except Exception as e:
        logger.debug(f"CGSPostKeyboardEvent 异常: {e}")
    return (False, "")


def _try_cgevent() -> Tuple[bool, str]:
    """Quartz CGEvent Cmd+Ctrl+Q"""
    try:
        import Quartz
        ctrl, cmd, q = 59, 55, 12
        flags = Quartz.kCGEventFlagMaskControl | Quartz.kCGEventFlagMaskCommand
        for k in (cmd, ctrl):
            Quartz.CGEventPost(Quartz.kCGHIDEventTap,
                Quartz.CGEventCreateKeyboardEvent(None, k, True))
            time.sleep(0.02)
        q_down = Quartz.CGEventCreateKeyboardEvent(None, q, True)
        Quartz.CGEventSetFlags(q_down, flags)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, q_down)
        time.sleep(0.08)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap,
            Quartz.CGEventCreateKeyboardEvent(None, q, False))
        time.sleep(0.02)
        for k in (ctrl, cmd):
            Quartz.CGEventPost(Quartz.kCGHIDEventTap,
                Quartz.CGEventCreateKeyboardEvent(None, k, False))
            time.sleep(0.02)
        return (True, "屏幕已锁定 (CGEvent Cmd+Ctrl+Q)")
    except Exception as e:
        logger.debug(f"CGEvent 异常: {e}")
    return (False, "")


def _try_cgsession() -> Tuple[bool, str]:
    path = _discover_cgsession()
    if not path:
        return (False, "")
    try:
        r = subprocess.run([path, "-suspend"], capture_output=True, timeout=5)
        if r.returncode == 0:
            return (True, "屏幕已锁定 (CGSession)")
    except Exception:
        pass
    return (False, "")


def _try_osascript() -> Tuple[bool, str]:
    try:
        r = subprocess.run(
            ["osascript", "-e",
             'tell application "System Events" to keystroke "q" using {command down, control down}'],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0 and not r.stderr.strip():
            return (True, "屏幕已锁定 (Cmd+Ctrl+Q)")
    except Exception:
        pass
    return (False, "")


def lock_screen() -> Tuple[bool, str]:
    """按优先级尝试锁屏，信任方法自身返回值"""
    strategies = [
        ("LockScreen Shortcut", _try_shortcut),
        ("ScreenSaverEngine", _try_sse),
        ("CGSPostKeyboardEvent Cmd+Ctrl+Q", _try_cgs_keyboard),
        ("CGEvent Cmd+Ctrl+Q", _try_cgevent),
        ("CGSession", _try_cgsession),
        ("osascript keystroke", _try_osascript),
    ]

    for name, func in strategies:
        ok, msg = func()
        if ok:
            logger.info(f"锁屏成功: {msg}")
            return (True, msg)

    logger.warning("所有锁屏方法均失败")
    return (False, "所有锁屏方法均失败")
