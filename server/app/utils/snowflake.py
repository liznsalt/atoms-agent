"""53 位雪花 ID：时间戳 42 位（毫秒，约 139 年）+ 机器 5 位 + 序列 6 位。

严格控制在 2^53 内 —— JavaScript Number 可精确表示（API JSON 直传 int 不丢精度，
前端无需字符串化）；SQLite INTEGER 天然 64 位兼容。机器位经 MACHINE_ID 环境变量
配置，多实例部署时错开。
"""

from __future__ import annotations

import os
import threading
import time

_EPOCH = 1735689600000  # 2025-01-01T00:00:00Z 的毫秒时间戳
_MACHINE_ID = int(os.getenv("MACHINE_ID", "1")) & 0x1F  # 5 位

_lock = threading.Lock()
_last_ms = 0
_seq = 0


def snowflake_id() -> int:
    """生成 53 位内单调递增的唯一 ID（同毫秒序列耗尽时自旋到下一毫秒）。"""
    global _last_ms, _seq
    with _lock:
        ms = time.time_ns() // 1_000_000
        if ms == _last_ms:
            _seq = (_seq + 1) & 0x3F  # 6 位序列
            if _seq == 0:  # 本毫秒 64 个序号耗尽：自旋等待下一毫秒
                while ms == _last_ms:
                    ms = time.time_ns() // 1_000_000
        else:
            _seq = 0
        _last_ms = ms
        return ((ms - _EPOCH) << 11) | (_MACHINE_ID << 6) | _seq
