"""
远程状态客户端 — SSH 周期性轮询远程锁屏状态（唯一通道，简单可靠）
"""
import asyncio
import logging
from typing import Optional, Callable, Awaitable

from remote.ssh_client import SSHClient, query_lock_state

logger = logging.getLogger("state_client")

import os
from dotenv import load_dotenv
load_dotenv()

REMOTE_IP = os.getenv("REMOTE_IP", "127.0.0.1")
REMOTE_USER = os.getenv("REMOTE_USER", "root")
POLL_INTERVAL_SECS = 3.0


class RemoteStateClient:
    def __init__(self, host: str = REMOTE_IP, user: str = REMOTE_USER):
        self.host = host
        self.user = user
        self._ssh: Optional[SSHClient] = None
        self._lock_state: Optional[bool] = None
        self._poll_task: Optional[asyncio.Task] = None
        self._running = False

    @property
    def lock_state(self) -> Optional[bool]:
        return self._lock_state

    def get_lock_state(self) -> Optional[bool]:
        if self._ssh is None:
            self._ssh = SSHClient(self.host, self.user)
        state = query_lock_state(self._ssh)
        if state is not None:
            old = self._lock_state
            self._lock_state = state
            if old is not None and old != state:
                logger.info(f"远程锁屏状态变更: {'locked' if state else 'unlocked'}")
        return self._lock_state

    async def start(self):
        if self._running:
            return
        self._running = True
        self._ssh = SSHClient(self.host, self.user)
        self.get_lock_state()
        logger.info(f"远程初始状态: {'locked' if self._lock_state else 'unlocked'}")
        self._poll_task = asyncio.ensure_future(self._poll_loop())

    async def stop(self):
        self._running = False
        if self._poll_task:
            self._poll_task.cancel()
        if self._ssh:
            self._ssh.close()
        logger.info("远程状态客户端已停止")

    async def _poll_loop(self):
        while self._running:
            await asyncio.sleep(POLL_INTERVAL_SECS)
            try:
                self.get_lock_state()
            except Exception as e:
                logger.warning(f"轮询异常: {e}")
