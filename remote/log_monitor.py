"""
远程日志监控 — 通过 SSH 执行 log stream 监听锁屏 event
实时检测 kAELockScreen / kAEUnlockScreen 事件
"""
import asyncio
import json
import logging
import socket
from typing import Optional, Callable, Awaitable

logger = logging.getLogger("log_monitor")

# log stream 过滤: loginwindow 进程的锁屏/解锁事件
LOG_STREAM_CMD = (
    "log stream --predicate 'process == \"loginwindow\"' "
    "--style json 2>/dev/null"
)

# 事件匹配关键词
LOCK_KEYWORDS = ["kAELockScreen", "com.apple.screenIsLocked", "ScreenIsLocked"]
UNLOCK_KEYWORDS = ["kAEUnlockScreen", "com.apple.screenIsUnlocked", "ScreenIsUnlocked"]


class LogMonitor:
    """远程日志监听器 — 通过 SSH log stream 实时检测锁屏事件"""

    def __init__(self, host: str = "x.x.x.x", user: str = "your_ssh_user"):
        self.host = host
        self.user = user
        self._running = False
        self._on_lock: Optional[Callable[[], Awaitable[None]]] = None
        self._on_unlock: Optional[Callable[[], Awaitable[None]]] = None

    def on_lock(self, callback: Callable[[], Awaitable[None]]):
        self._on_lock = callback

    def on_unlock(self, callback: Callable[[], Awaitable[None]]):
        self._on_unlock = callback

    async def start(self):
        """启动 log stream 监听（通过 SSH 建立 channel 流式读取）"""
        self._running = True
        import paramiko

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(self.host, username=self.user, timeout=10,
                       allow_agent=True, look_for_keys=True)

        transport = client.get_transport()
        if not transport:
            logger.error("无法建立 transport 连接")
            return

        channel = transport.open_session(timeout=10)
        channel.exec_command(LOG_STREAM_CMD)
        channel.settimeout(3)

        logger.info("log stream 监听已启动")

        try:
            while self._running:
                try:
                    line = channel.recv(4096).decode("utf-8", errors="replace")
                    if not line:
                        break
                    self._parse_line(line)
                except (socket.timeout, OSError):
                    continue
        except Exception as e:
            logger.warning(f"log stream 异常: {e}")
        finally:
            channel.close()
            client.close()
            logger.info("log stream 监听已停止")

    def stop(self):
        self._running = False

    def _parse_line(self, line: str):
        """解析 log stream JSON 行"""
        try:
            data = json.loads(line.strip())
        except json.JSONDecodeError:
            return

        event_msg = data.get("eventMessage", "") or data.get("message", "") or ""
        if not event_msg:
            return

        event_lower = event_msg.lower()

        # 检查是否锁屏
        for kw in LOCK_KEYWORDS:
            if kw.lower() in event_lower:
                if self._on_lock:
                    asyncio.ensure_future(self._on_lock())
                    logger.info(f"远程锁屏事件: {event_msg[:80]}")
                return

        # 检查是否解锁
        for kw in UNLOCK_KEYWORDS:
            if kw.lower() in event_lower:
                if self._on_unlock:
                    asyncio.ensure_future(self._on_unlock())
                    logger.info(f"远程解锁事件: {event_msg[:80]}")
                return
