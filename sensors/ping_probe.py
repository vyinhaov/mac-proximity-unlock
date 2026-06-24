"""
Ping 探测 — 周期性 ping 远程 MacBook IP，获取网络延迟
作为辅助信号，与蓝牙 RSSI 双信号融合
"""
import asyncio
import logging
import subprocess
import re
from typing import Tuple, Optional

logger = logging.getLogger("ping_probe")

import os
from dotenv import load_dotenv
load_dotenv()

REMOTE_IP = os.getenv("REMOTE_IP", "127.0.0.1")

# Ping 命令参数 (macOS: -c count, -t timeout 秒)
# 同 WiFi 环境下 ping 波动较大，给予充裕阈值
PING_COUNT = 2
PING_TIMEOUT = 2  # 秒


class PingProbe:
    """Ping 延迟探测"""

    def __init__(self, remote_ip: str = REMOTE_IP):
        self.remote_ip = remote_ip
        self._last_min_rtt: Optional[float] = None
        self._last_avg_rtt: Optional[float] = None
        self._consecutive_failures = 0

    async def probe(self) -> Optional[float]:
        """执行 ping 并返回平均 RTT (ms)，失败返回 None"""
        loop = asyncio.get_event_loop()
        try:
            rtt_stats = await loop.run_in_executor(None, self._do_ping)
            if rtt_stats:
                self._last_min_rtt = rtt_stats[0]
                self._last_avg_rtt = rtt_stats[1]
                self._consecutive_failures = 0
                logger.debug(f"Ping min={rtt_stats[0]:.1f}ms avg={rtt_stats[1]:.1f}ms")
                return rtt_stats[1]
            else:
                self._consecutive_failures += 1
                return None
        except Exception as e:
            self._consecutive_failures += 1
            logger.warning(f"Ping 探测异常: {e}")
            return None

    def _do_ping(self) -> Optional[Tuple[float, float]]:
        """执行实际 ping 命令，返回 (min_rtt, avg_rtt)"""
        cmd = [
            "/sbin/ping", "-c", str(PING_COUNT),
            "-t", str(PING_TIMEOUT), self.remote_ip
        ]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=PING_COUNT * PING_TIMEOUT + 2
            )
            if result.returncode != 0:
                return None
            # 解析 "round-trip min/avg/max/stddev = 0.472/0.755/1.215/0.244 ms"
            match = re.search(
                r"min/avg/max/(?:stddev|mdev)\s*=\s*([\d.]+)/([\d.]+)",
                result.stdout
            )
            if match:
                return (float(match.group(1)), float(match.group(2)))
            return None
        except subprocess.TimeoutExpired:
            return None

    @property
    def last_min_rtt(self) -> Optional[float]:
        return self._last_min_rtt

    @property
    def last_avg_rtt(self) -> Optional[float]:
        return self._last_avg_rtt

    @property
    def consecutive_failures(self) -> int:
        return self._consecutive_failures

    @property
    def is_reachable(self) -> bool:
        return self._consecutive_failures < 2
