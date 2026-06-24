"""
蓝牙扫描器 — system_profiler 文本输出解析远程 MacBook 经典蓝牙 RSSI
bleak 仅支持 BLE；XML 版本的 system_profiler 字段名不符预期
"""
import asyncio
import logging
import re
import subprocess
import time
from typing import Optional

logger = logging.getLogger("bluetooth_scanner")

import os
from dotenv import load_dotenv
load_dotenv()

REMOTE_BT_MAC = os.getenv("REMOTE_BT_MAC", "00:00:00:00:00:00")

_CACHE_TTL = 5.0
_cache_rssi: Optional[float] = None
_cache_time: float = 0.0


class KalmanFilter:
    def __init__(self, process_noise: float = 0.01, measurement_noise: float = 0.5):
        self.x = -60.0; self.p = 1.0; self.q = process_noise; self.r = measurement_noise

    def update(self, measurement: float) -> float:
        self.p += self.q
        k = self.p / (self.p + self.r)
        self.x += k * (measurement - self.x)
        self.p *= (1 - k)
        return self.x

    @property
    def value(self) -> float:
        return self.x


class BluetoothScanner:
    def __init__(self, remote_mac: str = REMOTE_BT_MAC):
        self.remote_mac = remote_mac.lower()
        self.kf = KalmanFilter()
        self._last_raw_rssi: Optional[float] = None

    async def scan_rssi(self, timeout: float = 3.0) -> Optional[float]:
        global _cache_rssi, _cache_time
        now = time.time()
        if now - _cache_time < _CACHE_TTL:
            return _cache_rssi

        try:
            loop = asyncio.get_event_loop()
            raw = await loop.run_in_executor(None, self._fetch_rssi)
            if raw is not None:
                self._last_raw_rssi = raw
                _cache_rssi = self.kf.update(raw)
                _cache_time = now
                logger.debug(f"RSSI raw={raw} filt={_cache_rssi:.0f}")
                return _cache_rssi

            if _cache_rssi is not None:
                logger.debug(f"RSSI miss → cached {_cache_rssi:.0f}")
            return _cache_rssi
        except Exception as e:
            logger.debug(f"BT err: {e}")
            return _cache_rssi

    def _fetch_rssi(self) -> Optional[float]:
        """system_profiler SPBluetoothDataType 文本输出 → 解析 RSSI"""
        try:
            r = subprocess.run(
                ["system_profiler", "SPBluetoothDataType"],
                capture_output=True, timeout=8,
            )
            if r.returncode != 0:
                return None

            lines = r.stdout.decode('utf-8', errors='replace')
            # Find the device block by MAC address pattern
            # Format: Address: xx:xx:xx:xx:xx:xx\n              RSSI: -34
            mac_upper = self.remote_mac.upper()
            # Look for "Address: XX:XX:XX:XX:XX:XX" then "RSSI: NN" in following lines
            pattern = rf'Address:\s*{re.escape(mac_upper)}.*?RSSI:\s*(-?\d+)'
            m = re.search(pattern, lines, re.DOTALL)
            if m:
                return float(m.group(1))
            return None
        except Exception as e:
            logger.debug(f"fetch err: {e}")
            return None

    @property
    def last_raw_rssi(self) -> Optional[float]:
        return self._last_raw_rssi

    def reset(self):
        global _cache_rssi, _cache_time
        self.kf = KalmanFilter()
        self._last_raw_rssi = None
        _cache_rssi = None; _cache_time = 0.0
