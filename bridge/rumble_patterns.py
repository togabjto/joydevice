"""bridge/rumble.py (フォールバック実行時) と bridge/rumble_daemon.py (常駐サーバー) の
両方が参照する振動パターン定義。経路によって定義がずれると手触りが変わってしまうため
ここに一本化している。
"""
from __future__ import annotations

from pathlib import Path

# rumble.py/notify_hook.py が常駐デーモンへ高速パスで接続する際に使うUnixドメインソケットのパス。
SOCKET_PATH = Path.home() / ".joycon_rumble.sock"

# デーモンへの接続確立に使うタイムアウト(秒)。デーモンが起動しているかどうかの
# 判定に使うだけなので短く諦める。
DAEMON_CONNECT_TIMEOUT_S = 0.3

# パターン名 -> [(low_freq, high_freq, duration_ms, パルス後の無音秒数), ...]
RUMBLE_PATTERNS: dict[str, list[tuple[float, float, int, float]]] = {
    "working": [(0.4, 0.4, 80, 0.05)],
    "permission_prompt": [(0.8, 0.8, 400, 0.1)],
    # 入力待ち(アイドル)。許可待ちの長い一発と区別できるよう軽い3連タップにする。
    "waiting_input": [(0.5, 0.5, 100, 0.1), (0.5, 0.5, 100, 0.1), (0.5, 0.5, 100, 0.1)],
    "task_done": [(0.8, 0.8, 120, 0.25), (0.8, 0.8, 120, 0.1)],
    "default": [(0.5, 0.5, 250, 0.1)],
}
