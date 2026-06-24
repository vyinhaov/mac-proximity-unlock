"""
动作执行器 — 距离感应 + 远程锁屏状态双信号融合
- 蓝牙 RSSI + Ping 延迟 → DistanceEngine FSM → NEAR/MID/FAR
- SSH 轮询远程锁屏状态 → locked/unlocked
- 锁定: 远程锁屏 或 距离变为 FAR → 本机锁屏
- 解锁: 远程解锁 且 距离为 NEAR → 本机解锁
"""
import asyncio
import logging
import time
from typing import Optional

from remote.state_client import RemoteStateClient
from actions.locker import lock_screen
from actions.unlocker import unlock_screen
from sensors.distance_engine import DistanceEngine, DistanceState
from sensors.bluetooth_scanner import BluetoothScanner
from sensors.ping_probe import PingProbe

logger = logging.getLogger("executor")

DEBOUNCE_SECS = 5.0
POLL_INTERVAL_SECS = 2.0
SENSOR_INTERVAL_SECS = 3.0  # BT/ping 采样间隔


class ProximityExecutor:
    def __init__(self):
        self.remote_client = RemoteStateClient()
        self.distance_engine = DistanceEngine()
        self.bt_scanner = BluetoothScanner()
        self.ping_probe = PingProbe()

        self._last_lock_time = 0.0
        self._last_unlock_time = 0.0
        self._prev_remote_state: Optional[bool] = None
        self._running = False

        # 传感器后台任务
        self._sensor_task: Optional[asyncio.Task] = None

    async def start(self):
        if self._running:
            return
        self._running = True
        logger.info("ProximityLock 启动")

        # 启动远程状态轮询
        await self.remote_client.start()
        self._prev_remote_state = self.remote_client.lock_state

        # 启动距离传感器后台任务
        self._sensor_task = asyncio.ensure_future(self._sensor_loop())

        await self._main_loop()

    async def stop(self):
        self._running = False
        if self._sensor_task:
            self._sensor_task.cancel()
        await self.remote_client.stop()
        self.distance_engine.reset()
        logger.info("ProximityLock 已停止")

    async def _sensor_loop(self):
        """后台任务: 周期性采样 BT RSSI + Ping → DistanceEngine"""
        logger.info("距离传感器循环启动")
        while self._running:
            try:
                # 并行采样
                rssi, ping_ms = await asyncio.gather(
                    self.bt_scanner.scan_rssi(timeout=2.5),
                    self.ping_probe.probe(),
                    return_exceptions=True,
                )
                if isinstance(rssi, Exception):
                    rssi = None
                if isinstance(ping_ms, Exception):
                    ping_ms = None

                # FSM 更新
                new_state = self.distance_engine.update(rssi, ping_ms)

                logger.debug(
                    f"传感器: RSSI={rssi} ping={ping_ms}ms → {new_state.value}"
                )
            except Exception as e:
                logger.debug(f"传感器采样异常: {e}")

            await asyncio.sleep(SENSOR_INTERVAL_SECS)

    async def _main_loop(self):
        logger.info(f"主循环启动 (间隔 {POLL_INTERVAL_SECS}s)")
        while self._running:
            await asyncio.sleep(POLL_INTERVAL_SECS)

            remote_locked = self.remote_client.lock_state
            if remote_locked is None:
                continue

            dist_state = self.distance_engine.state

            # ── 远程状态变更 ──
            if self._prev_remote_state is not None and remote_locked != self._prev_remote_state:
                logger.info(
                    f"检测到状态变化: {'locked' if self._prev_remote_state else 'unlocked'} "
                    f"→ {'locked' if remote_locked else 'unlocked'} "
                    f"(距离={dist_state.value})"
                )
                if remote_locked:
                    # 远程锁屏 → 本机立即锁屏（安全优先，不管距离）
                    await self._try_lock()
                else:
                    # 远程解锁 → 仅在距离为 NEAR 时解锁本机
                    await self._try_unlock()

            self._prev_remote_state = remote_locked

            # ── 远离自动锁屏（距离驱动，不依赖远程状态） ──
            if (dist_state == DistanceState.FAR
                    and self.distance_engine.transition_near_to_far
                    and self.distance_engine.stable_seconds() > 3.0
                    and not remote_locked):
                # 用户远离但远程未锁屏？可能远程 Mac 还在用，不强制锁
                pass

            # 远离 + 远程也锁了 → 确保本机已锁
            if (dist_state == DistanceState.FAR
                    and remote_locked
                    and self.distance_engine.transition_near_to_far):
                await self._try_lock()

    async def _try_lock(self):
        now = time.time()
        if now - self._last_lock_time < DEBOUNCE_SECS:
            return
        success, msg = lock_screen()
        if success:
            self._last_lock_time = now
        logger.info(f"锁屏: {msg}")

    async def _try_unlock(self):
        now = time.time()
        if now - self._last_unlock_time < DEBOUNCE_SECS:
            return

        dist_state = self.distance_engine.state

        # 核心产品逻辑: 只在距离为 NEAR 时解锁
        if dist_state != DistanceState.NEAR:
            logger.info(
                f"跳过解锁: 距离={dist_state.value} (需要 NEAR)"
            )
            return

        success, msg = unlock_screen()
        if success:
            self._last_unlock_time = now
        logger.info(f"解锁: {msg}")

    @property
    def is_running(self) -> bool:
        return self._running
