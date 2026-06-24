"""
CGSPostKeyboardEvent 键盘模拟 — WindowServer 级别注入，绕过 SecureEventInput
这是锁屏/解锁场景下唯一可靠的方法
"""
import ctypes
import time
from typing import Tuple

_CGS = None
_CGS_CONNECTION = None
_available = None


def _load_cgs():
    global _CGS
    if _CGS is None:
        _CGS = ctypes.CDLL(
            '/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics'
        )
    return _CGS


def _get_connection() -> int:
    """获取当前进程的 CGS 连接 ID，用于 WindowServer 级别键盘注入"""
    global _CGS_CONNECTION
    if _CGS_CONNECTION is not None:
        return _CGS_CONNECTION
    cgs = _load_cgs()
    try:
        cgs.CGSMainConnectionID.restype = ctypes.c_uint32
        cgs.CGSMainConnectionID.argtypes = []
        _CGS_CONNECTION = cgs.CGSMainConnectionID()
    except Exception:
        _CGS_CONNECTION = 0
    return _CGS_CONNECTION


def _is_available() -> bool:
    global _available
    if _available is not None:
        return _available
    try:
        cgs = _load_cgs()
        cgs.CGSPostKeyboardEvent.argtypes = [
            ctypes.c_uint32,   # connection id
            ctypes.c_uint16,   # CGKeyCode
            ctypes.c_bool,     # keyDown
        ]
        cgs.CGSPostKeyboardEvent.restype = ctypes.c_int32
        conn = _get_connection()
        if conn == 0:
            import logging
            logging.getLogger("cgs_keyboard").warning(
                "CGSMainConnectionID 返回 0，CGSPostKeyboardEvent 不可用"
            )
            _available = False
        else:
            _available = True
    except Exception as e:
        import logging
        logging.getLogger("cgs_keyboard").warning(
            f"CGSPostKeyboardEvent 初始化失败: {e}"
        )
        _available = False
    return _available


def _post_key(keycode: int, key_down: bool) -> None:
    if not _is_available():
        return
    conn = _get_connection()
    if conn == 0:
        return
    try:
        _CGS.CGSPostKeyboardEvent(conn, keycode, key_down)
    except Exception:
        pass


# ── 字符 → macOS keycode + shift 映射（US 键盘）────────────────────────

KC_A = 0;    KC_B = 11;   KC_C = 8;    KC_D = 2;    KC_E = 14
KC_F = 3;    KC_G = 5;    KC_H = 4;    KC_I = 34;   KC_J = 38
KC_K = 40;   KC_L = 37;   KC_M = 46;   KC_N = 45;   KC_O = 31
KC_P = 35;   KC_Q = 12;   KC_R = 15;   KC_S = 1;    KC_T = 17
KC_U = 32;   KC_V = 9;    KC_W = 13;   KC_X = 7;    KC_Y = 16
KC_Z = 6

_LETTER_KC = {
    'a': KC_A, 'b': KC_B, 'c': KC_C, 'd': KC_D, 'e': KC_E,
    'f': KC_F, 'g': KC_G, 'h': KC_H, 'i': KC_I, 'j': KC_J,
    'k': KC_K, 'l': KC_L, 'm': KC_M, 'n': KC_N, 'o': KC_O,
    'p': KC_P, 'q': KC_Q, 'r': KC_R, 's': KC_S, 't': KC_T,
    'u': KC_U, 'v': KC_V, 'w': KC_W, 'x': KC_X, 'y': KC_Y,
    'z': KC_Z,
}

_DIGIT_KC = {'1': 18, '2': 19, '3': 20, '4': 21, '5': 22,
             '6': 23, '7': 24, '8': 25, '9': 26, '0': 29}

_SYMBOL_MAP = {
    '-': (27, False),  '=': (24, False),
    '[': (33, False),  ']': (30, False),
    '\\': (42, False), ';': (41, False),
    "'": (39, False),  ',': (43, False),
    '.': (47, False),  '/': (44, False),
    '`': (50, False),  ' ': (49, False),
    '!': (18, True),   '@': (19, True),   '#': (20, True),
    '$': (21, True),   '%': (22, True),   '^': (23, True),
    '&': (24, True),   '*': (25, True),   '(': (26, True),
    ')': (29, True),   '_': (27, True),   '+': (24, True),
    '{': (33, True),   '}': (30, True),   '|': (42, True),
    ':': (41, True),   '"': (39, True),   '<': (43, True),
    '>': (47, True),   '?': (44, True),   '~': (50, True),
}

KC_RETURN = 36
KC_ESCAPE = 53
KC_SPACE = 49
KC_SHIFT_L = 56
KC_CTRL_L = 59
KC_CMD_L = 55
KC_OPT_L = 58


def _char_to_keycode(ch: str) -> Tuple[int, bool]:
    lo = ch.lower()
    if lo in _LETTER_KC:
        return _LETTER_KC[lo], ch.isupper()
    if ch in _DIGIT_KC:
        return _DIGIT_KC[ch], False
    if ch in _SYMBOL_MAP:
        return _SYMBOL_MAP[ch]
    return 0, False


def type_text(text: str, interval: float = 0.02) -> None:
    for ch in text:
        if ch == '\n' or ch == '\r':
            _post_key(KC_RETURN, True)
            time.sleep(0.008)
            _post_key(KC_RETURN, False)
            time.sleep(interval)
            continue

        kc, shift = _char_to_keycode(ch)
        if kc == 0 and ch not in (' ', '\n', '\r'):
            continue

        if shift:
            _post_key(KC_SHIFT_L, True)
            time.sleep(0.005)

        _post_key(kc, True)
        time.sleep(0.005)
        _post_key(kc, False)
        time.sleep(interval)

        if shift:
            _post_key(KC_SHIFT_L, False)
            time.sleep(0.005)


def send_combo(modifiers, keycode, hold: float = 0.05) -> None:
    for m in modifiers:
        _post_key(m, True)

    _post_key(keycode, True)
    time.sleep(hold)
    _post_key(keycode, False)

    for m in reversed(modifiers):
        _post_key(m, False)


def lock_screen_cgs() -> bool:
    if not _is_available():
        return False
    try:
        send_combo([KC_CMD_L, KC_CTRL_L], KC_Q, hold=0.08)
        return True
    except Exception:
        return False
