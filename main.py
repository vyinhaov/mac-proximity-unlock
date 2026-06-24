#!/usr/bin/env python3
"""
mac-proximity-unlock — 主入口
两台 MacBook 距离感应，本机跟随远程解锁/锁屏

用法:
    python3 main.py                # 启动（前台）
    python3 main.py --check        # 检查环境就绪
    python3 main.py --init-keychain # 初始化 Keychain 密码
"""
import argparse
import logging
import os
import subprocess
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(_PROJECT_ROOT))

LOG_DIR = Path.home() / "Library" / "Logs" / "mac-auto-unlock"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "app.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("main")

PID_FILE = Path("/tmp") / "mac-proximity-unlock.pid"


def _acquire_lock() -> bool:
    """PID 文件锁：防止多实例并发"""
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            os.kill(pid, 0)
            logger.error(f"已有实例运行中 (PID {pid})，退出")
            return False
        except (ValueError, ProcessLookupError):
            PID_FILE.unlink(missing_ok=True)
        except OSError:
            pass
    PID_FILE.write_text(str(os.getpid()))
    return True


def _release_lock():
    try:
        PID_FILE.unlink(missing_ok=True)
    except Exception:
        pass


def _check_accessibility() -> bool:
    """检查 Accessibility 权限"""
    try:
        import Quartz
        event = Quartz.CGEventCreate(None)
        return event is not None
    except Exception:
        return False


def _check_ssh_key() -> bool:
    """检查 SSH 免密是否配置"""
    import os
    host = f"{os.getenv('REMOTE_USER', 'root')}@{os.getenv('REMOTE_IP', '127.0.0.1')}"
    try:
        result = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5",
             host, "echo ok"],
            capture_output=True, text=True, timeout=10,
        )
        return result.returncode == 0 and "ok" in result.stdout
    except Exception:
        return False


def _check_keychain_password() -> bool:
    """检查 Keychain 中是否有密码"""
    try:
        from actions.unlocker import read_password_from_keychain
        return read_password_from_keychain() is not None
    except Exception:
        return False


def check_environment():
    """检查环境就绪"""
    print("=== 环境检查 ===\n")

    for mod in ["Quartz", "bleak", "paramiko"]:
        try:
            __import__(mod)
            print(f"  OK {mod}")
        except ImportError:
            print(f"  MISS {mod}")

    if _check_accessibility():
        print("  OK Accessibility")
    else:
        print("  NEED Accessibility")

    if _check_ssh_key():
        print("  OK SSH -> x.x.x.x")
    else:
        print("  NEED SSH: ssh-copy-id your_ssh_user@x.x.x.x")

    if _check_keychain_password():
        print("  OK Keychain password")
    else:
        print("  NEED Keychain: python3 main.py --init-keychain")

    print()


def init_keychain():
    """引导用户输入密码存入 Keychain"""
    import getpass
    from actions.unlocker import store_password_to_keychain

    print("=== Keychain 密码初始化 ===\n")
    pw1 = getpass.getpass("输入 Mac 登录密码: ")
    pw2 = getpass.getpass("再次输入确认: ")
    if pw1 != pw2:
        print("ERROR: 两次输入不一致")
        sys.exit(1)
    if store_password_to_keychain(pw1):
        print("OK 密码已安全存储")
    else:
        print("ERROR: 存储失败")
        sys.exit(1)


def _show_accessibility_guide():
    """显示 Accessibility 权限引导"""
    print("\n需要辅助功能权限才能自动解锁。")
    print("请打开: 系统设置 -> 隐私与安全性 -> 辅助功能")
    print("添加: /usr/bin/python3")
    print("设置完成后重新运行本程序。\n")


def main():
    parser = argparse.ArgumentParser(description="Mac 近距解锁")
    parser.add_argument("--check", action="store_true", help="检查环境就绪")
    parser.add_argument("--init-keychain", action="store_true",
                        help="初始化 Keychain 密码")
    args = parser.parse_args()

    if args.check:
        check_environment()
        return

    if args.init_keychain:
        init_keychain()
        return

    if not _acquire_lock():
        sys.exit(1)

    check_environment()

    if not _check_accessibility():
        _show_accessibility_guide()

    if not _check_ssh_key():
        print("WARNING: SSH 免密未配置，远程状态查询会失败")
        print("请运行: ssh-copy-id your_ssh_user@x.x.x.x")

    if not _check_keychain_password():
        print("WARNING: Keychain 密码未设置，自动解锁会失败")
        print("请运行: python3 main.py --init-keychain")

    logger.info("=" * 50)
    logger.info("mac-proximity-unlock 启动")
    logger.info("=" * 50)

    import asyncio
    from actions.executor import ProximityExecutor

    executor = ProximityExecutor()

    try:
        asyncio.run(executor.start())
    except KeyboardInterrupt:
        logger.info("收到退出信号")
    finally:
        asyncio.run(executor.stop())
        _release_lock()
        logger.info("mac-proximity-unlock 已停止")


if __name__ == "__main__":
    main()
