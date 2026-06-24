"""
距离引擎 — FSM 状态机，融合蓝牙 RSSI + Ping 延迟双信号
判定本机与远程 MacBook "近/中/远" 距离状态

规则:
- "近": 任一信号满足 (RSSI > -55dBm 或 ping < 200ms)
- "远": 连续 6 次无信号
- RSSI 为主信号 (物理距离相关)，Ping 为辅助
"""
import logging
import time
from enum import Enum
from typing import Optional

logger = logging.getLogger("distance_engine")

RSSI_NEAR_THRESHOLD = -55      # near: RSSI > -55 dBm
PING_NEAR_THRESHOLD_MS = 200.0 # near: ping < 200ms (辅助)
FAR_LOOKBACK = 6               # 连续 6 次无信号 → FAR (≈18s, 防抖动)


class DistanceState(Enum):
    UNKNOWN = "unknown"   # 初始/设备未发现
    NEAR = "near"         # 近距离
    MID = "mid"           # 中等距离 (过渡)
    FAR = "far"           # 远距离


class DistanceEngine:
    """距离状态机 — 双信号融合"""

    def __init__(self, rssi_near_threshold: float = RSSI_NEAR_THRESHOLD,
                 ping_near_threshold_ms: float = PING_NEAR_THRESHOLD_MS,
                 far_lookback: int = FAR_LOOKBACK):
        self.rssi_near_threshold = rssi_near_threshold
        self.ping_near_threshold_ms = ping_near_threshold_ms
        self.far_lookback = far_lookback

        self.state = DistanceState.UNKNOWN
        self._near_votes: list = []  # 滑动窗口: 每次是否近
        self._last_state_change: float = 0.0
        self._last_rssi: Optional[float] = None
        self._last_ping: Optional[float] = None

    def update(self, rssi: Optional[float], ping_ms: Optional[float]) -> DistanceState:
        """更新双信号输入，返回当前距离状态"""
        self._last_rssi = rssi
        self._last_ping = ping_ms

        is_rssi_near = rssi is not None and rssi > self.rssi_near_threshold
        is_ping_near = ping_ms is not None and ping_ms < self.ping_near_threshold_ms

        # 双信号同时满足 → 近（最可靠）
        is_both = is_rssi_near and is_ping_near

        # 任一信号有效 → 候选近（蓝牙 RSSI 可能为 None，ping 为主信号）
        is_signal_any = is_rssi_near or is_ping_near

        # 没有任何有效信号 → 未知距离
        no_signal = rssi is None and ping_ms is None

        # 入队近投票 (任一信号满足即计入)
        self._near_votes.append(1 if is_signal_any else 0)
        if len(self._near_votes) > self.far_lookback + 2:
            self._near_votes.pop(0)

        previous_state = self.state

        if self.state == DistanceState.UNKNOWN:
            # 从 UNKNOWN 首次判定: 任一信号满足即 NEAR
            if is_signal_any:
                self.state = DistanceState.NEAR
            elif no_signal:
                self.state = DistanceState.FAR
            else:
                self.state = DistanceState.FAR

        elif self.state in (DistanceState.NEAR, DistanceState.MID):
            # 滑动窗口投票: 最近 N 次全部不满足 → FAR
            recent_votes = self._near_votes[-self.far_lookback:]
            if len(recent_votes) >= self.far_lookback and sum(recent_votes) == 0:
                self.state = DistanceState.FAR

        elif self.state == DistanceState.FAR:
            # 从 FAR → NEAR: 任一信号恢复即可
            if is_signal_any:
                self.state = DistanceState.NEAR

        if self.state != previous_state:
            self._last_state_change = time.time()
            if previous_state != DistanceState.UNKNOWN:
                logger.info(
                    f"距离状态变更: {previous_state.value} → {self.state.value} "
                    f"(RSSI={rssi}, ping={ping_ms})"
                )

        logger.debug(f"距离引擎: state={self.state.value} "
                     f"rssi_near={is_rssi_near} ping_near={is_ping_near}")
        return self.state

    @property
    def is_near(self) -> bool:
        return self.state == DistanceState.NEAR

    @property
    def is_far(self) -> bool:
        return self.state == DistanceState.FAR

    @property
    def transition_near_to_far(self) -> bool:
        """刚刚从近变远（仅在有近距历史记录时才返回 True）"""
        had_near = any(v == 1 for v in self._near_votes)
        return had_near and self._near_votes.count(1) == 0 and self.state == DistanceState.FAR

    def stable_seconds(self) -> float:
        """当前状态维持秒数"""
        return time.time() - self._last_state_change

    def reset(self):
        self.state = DistanceState.UNKNOWN
        self._near_votes.clear()
        self._last_state_change = time.time()
