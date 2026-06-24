"""
解锁: shortcuts run UnlockMac (优先) → CGSPostKeyboardEvent (备用)
Shortcuts 有独立 entitlement，AppleScript keystroke 可送锁屏界面。
"""
import subprocess, time, ctypes, logging, os
from typing import Optional, Tuple

logger = logging.getLogger("unlocker")

KEYCHAIN_SERVICE = "MacAutoUnlock"
KEYCHAIN_ACCOUNT = "local_mac"
UNLOCK_SHORTCUT = "UnlockMac"

# ── CGSPostKeyboardEvent (备用) ──────────────────────────

def _cgs_key(kc: int, down: bool) -> None:
    """在获新连接后调用 CGSPostKeyboardEvent"""
    try:
        cgs = ctypes.CDLL('/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics')
        cgs.CGSMainConnectionID.restype = ctypes.c_uint32
        conn = cgs.CGSMainConnectionID()
        cgs.CGSPostKeyboardEvent.argtypes = [ctypes.c_uint32, ctypes.c_uint16, ctypes.c_bool]
        cgs.CGSPostKeyboardEvent.restype = ctypes.c_int32
        cgs.CGSPostKeyboardEvent(conn, kc, down)
    except Exception:
        pass

_LETTER={'a':0,'b':11,'c':8,'d':2,'e':14,'f':3,'g':5,'h':4,'i':34,'j':38,'k':40,'l':37,'m':46,'n':45,'o':31,'p':35,'q':12,'r':15,'s':1,'t':17,'u':32,'v':9,'w':13,'x':7,'y':16,'z':6}
_DIGIT={'1':18,'2':19,'3':20,'4':21,'5':22,'6':23,'7':24,'8':25,'9':26,'0':29}
_SYM={'-':(27,0),'=':(24,0),'[':(33,0),']':(30,0),'\\':(42,0),';':(41,0),"'":(39,0),',':(43,0),'.':(47,0),'/':(44,0),'`':(50,0),' ':(49,0),'!':(18,1),'@':(19,1),'#':(20,1),'$':(21,1),'%':(22,1),'^':(23,1),'&':(24,1),'*':(25,1),'(':(26,1),')':(29,1),'_':(27,1),'+':(24,1),'{':(33,1),'}':(30,1),'|':(42,1),':':(41,1),'"':(39,1),'<':(43,1),'>':(47,1),'?':(44,1),'~':(50,1)}

def _type_cgs(pw: str) -> None:
    """CGSPostKeyboardEvent 后备。每次调用获取新 CGS 连接（avoid stale conn segfault）"""
    try:
        import Quartz as Q
        pt = Q.CGEventGetLocation(Q.kCGEventSourceStateHIDSystemState)
        for dx in [5,-5,10,-10,3]: 
            Q.CGWarpMouseCursorPosition((pt.x+dx, pt.y)); time.sleep(0.03)
        Q.CGWarpMouseCursorPosition((pt.x, pt.y))
    except: pass
    time.sleep(2)
    
    for _ in range(3):
        _cgs_key(53, True); _cgs_key(53, False); time.sleep(0.3)
    time.sleep(1)
    _cgs_key(59, True); time.sleep(0.03)
    _cgs_key(49, True); time.sleep(0.05)
    _cgs_key(49, False); time.sleep(0.03)
    _cgs_key(59, False); time.sleep(0.5)
    
    for ch in pw:
        lo=ch.lower()
        if lo in _LETTER: kc,sh=_LETTER[lo],ch.isupper()
        elif ch in _DIGIT: kc,sh=_DIGIT[ch],False
        elif ch in _SYM: kc,sh=_SYM[ch][0],bool(_SYM[ch][1])
        else: continue
        if sh: _cgs_key(56, True)
        _cgs_key(kc, True); _cgs_key(kc, False); time.sleep(0.04)
        if sh: _cgs_key(56, False)
    _cgs_key(36, True); _cgs_key(36, False); time.sleep(0.2)
    _cgs_key(36, True); _cgs_key(36, False)
    time.sleep(3)

# ── Shortcuts 解锁 (主力) ─────────────────────────────────

def _check_shortcut() -> bool:
    try:
        r = subprocess.run(["shortcuts", "list"], capture_output=True, text=True, timeout=5)
        return UNLOCK_SHORTCUT in r.stdout
    except: return False

def _print_setup_guide() -> None:
    print("""
╔══════════════════════════════════════════════╗
║       首次设置: 创建 UnlockMac Shortcut       ║
╠══════════════════════════════════════════════╣
║  1. 打开 Shortcuts app                       ║
║  2. 点 + 新建, 命名 "UnlockMac"              ║
║  3. 搜索 "Run AppleScript", 添加            ║
║  4. 粘贴以下脚本:                            ║
║                                              ║
║  on run                                      ║
║    set pw to ""                              ║
║    try                                       ║
║      set pw to (do shell script              ║
║        "cat /tmp/unlock_pw.txt")             ║
║    end try                                   ║
║    if pw is "" then                          ║
║      display dialog "Test:"                  ║
║        default answer ""                     ║
║        with hidden answer                    ║
║      set pw to text returned of result       ║
║    end if                                    ║
║    if pw is not "" then                      ║
║      tell app "System Events"                ║
║        tell process "loginwindow"            ║
║          set frontmost to true               ║
║        end tell                              ║
║        delay 0.5                             ║
║        keystroke pw                          ║
║        delay 0.2                             ║
║        keystroke return                      ║
║      end tell                                ║
║    end if                                    ║
║  end run                                     ║
║                                              ║
║  5. 保存 (Cmd+S), 关闭 Shortcuts             ║
║  6. 重新运行 python3 main.py                ║
╚══════════════════════════════════════════════╝
""", flush=True)

PWFILE = "/tmp/unlock_pw.txt"

def _unlock_shortcut(pw: str) -> Tuple[bool, str]:
    """Write pw to /tmp/unlock_pw.txt → shortcuts run UnlockMac (no args)"""
    try:
        with open(PWFILE, 'w') as f:
            f.write(pw)
        os.chmod(PWFILE, 0o600)
        
        print(f"[unlocker] shortcuts run {UNLOCK_SHORTCUT}...", flush=True)
        r = subprocess.run(
            ["shortcuts", "run", UNLOCK_SHORTCUT],
            capture_output=True, text=True, timeout=30,
        )
        os.unlink(PWFILE)
        
        if r.returncode == 0:
            time.sleep(2)
            return (True, "unlocked (Shortcut)")
        logger.warning(f"shortcuts failed: rc={r.returncode} {r.stderr[:200]}")
        return (False, f"shortcut err: {r.stderr[:100]}")
    except Exception as e:
        try: os.unlink(PWFILE)
        except: pass
        return (False, str(e))

# ── API ───────────────────────────────────────────────────

def read_password_from_keychain() -> Optional[str]:
    try:
        r = subprocess.run(["security","find-generic-password","-s",KEYCHAIN_SERVICE,
                            "-a",KEYCHAIN_ACCOUNT,"-w"], capture_output=True, text=True, timeout=5)
        return r.stdout.strip() if r.returncode==0 and r.stdout.strip() else None
    except: return None

def store_password_to_keychain(pw: str) -> bool:
    try:
        subprocess.run(["security","delete-generic-password","-s",KEYCHAIN_SERVICE,
                        "-a",KEYCHAIN_ACCOUNT], capture_output=True, timeout=5)
        r = subprocess.run(["security","add-generic-password","-s",KEYCHAIN_SERVICE,
                            "-a",KEYCHAIN_ACCOUNT,"-w",pw,"-U"], capture_output=True, text=True, timeout=5)
        return r.returncode==0
    except: return False

def is_screen_locked() -> bool:
    import ctypes
    try:
        cg=ctypes.CDLL('/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics')
        cf=ctypes.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
        cg.CGSessionCopyCurrentDictionary.restype=ctypes.c_void_p
        cf.CFDictionaryGetValue.restype=ctypes.c_void_p; cf.CFDictionaryGetValue.argtypes=[ctypes.c_void_p,ctypes.c_void_p]
        cf.CFBooleanGetValue.restype=ctypes.c_bool; cf.CFBooleanGetValue.argtypes=[ctypes.c_void_p]
        cf.CFRelease.restype=None; cf.CFRelease.argtypes=[ctypes.c_void_p]
        cf.CFStringCreateWithCString.restype=ctypes.c_void_p; cf.CFStringCreateWithCString.argtypes=[ctypes.c_void_p,ctypes.c_char_p,ctypes.c_int32]
        d=cg.CGSessionCopyCurrentDictionary()
        if not d: return True
        k=cf.CFStringCreateWithCString(None,b'CGSSessionScreenIsLocked',0x08000100)
        v=cf.CFDictionaryGetValue(d,k); l=cf.CFBooleanGetValue(v) if v else 0
        cf.CFRelease(k); cf.CFRelease(d)
        return bool(l)
    except: return True

def unlock_screen() -> Tuple[bool, str]:
    # 安全护栏：屏幕未锁绝不输入密码（防多实例泄密）
    if not is_screen_locked():
        return (True, "already unlocked")

    try: subprocess.run(['pkill','-x','ScreenSaverEngine'], capture_output=True, timeout=3)
    except: pass
    time.sleep(1)
    if not is_screen_locked():
        return (True, "already unlocked (dismissed)")

    pw = read_password_from_keychain()
    if not pw: return (False, "Keychain empty")
    
    # 策略 1: Shortcuts (主力, 有 entitlement)
    if _check_shortcut():
        print("[unlocker] Shortcut...", flush=True)
        ok, msg = _unlock_shortcut(pw)
        if ok: return (True, msg)
        logger.warning(f"Shortcut failed: {msg}")
    else:
        _print_setup_guide()
        logger.warning("UnlockMac Shortcut not found")
    
    # 策略 2: CGSPostKeyboardEvent (备用)
    print("[unlocker] CGSPostKeyboardEvent fallback...", flush=True)
    _type_cgs(pw)
    
    # 验证 (caffeinate 防 display sleep)
    cafe = subprocess.Popen(['caffeinate','-d','-t','10'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ok = False
    for _ in range(8):
        time.sleep(1)
        if not is_screen_locked():
            ok = True; break
    cafe.terminate()
    
    if ok:
        print("[unlocker] ✓", flush=True)
        return (True, "unlocked (CGS)")
    print("[unlocker] ✗", flush=True)
    return (False, "all methods failed")
