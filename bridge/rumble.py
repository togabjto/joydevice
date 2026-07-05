"""
Joy-Conの振動(ランブル)を実行する薄いレイヤー。

core.joycon_listener はボタン入力の常時監視に特化しており、プロセスを常駐させる
前提で作られている。一方こちらは「Claude Codeのhookから短命プロセスとして
呼ばれ、一度だけ振動させて終了する」用途に特化しているため、あえて別モジュールに分離している。

ただし短命プロセスとして毎回 `pygame.joystick.init()` からJoy-Conを探索し直すと
0.5〜0.8秒ほどかかる(SDL側のデバイス列挙が重い)。許可待ち通知のような即時性が
欲しい用途ではこれが無視できない遅延になるため、まず rumble_daemon.py (デバイス
ハンドルを保持したまま待ち受ける常駐プロセス) にソケット経由で振動を依頼する
高速パスを試し、デーモンが起動していない場合のみここでの自前初期化にフォールバック
する。
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

# 単体スクリプトとして実行されたとき(cwdがbridge/になる)でも
# core パッケージ(プロジェクトルート直下)をimportできるようにする。
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pygame

from bridge.rumble_patterns import RUMBLE_PATTERNS, SOCKET_PATH
from core.config_manager import load_joycon_map

# hookが実際に発火し、振動処理が最後まで走ったかを物理的な感覚に頼らず追跡するための
# デバッグログ。振動が「感じられない」原因がhook配線側かハードウェア側かを切り分けるために使う。
LOG_PATH = Path(__file__).resolve().parent / "notify.log"
DAEMON_SCRIPT = Path(__file__).resolve().parent / "rumble_daemon.py"
# 接続確立はデーモンが起動しているかどうかの判定なので短く諦める。応答待ちは
# 振動パターンの再生時間(最長でも1秒未満)より長く取り、実行中に取りこぼして
# フォールバックと二重に振動しないようにする。
DAEMON_CONNECT_TIMEOUT_S = 0.3
DAEMON_RESPONSE_TIMEOUT_S = 2.0


def _log(message: str) -> None:
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n")
    except OSError:
        pass


def _find_joystick(hint: str) -> pygame.joystick.JoystickType | None:
    best = None
    for i in range(pygame.joystick.get_count()):
        js = pygame.joystick.Joystick(i)
        js.init()
        if hint and hint.lower() in js.get_name().lower():
            return js
        if best is None:
            best = js
    return best


def _try_daemon(pattern_name: str) -> bool | None:
    """常駐デーモン経由の高速パス。デーモンが起動していなければNoneを返す。"""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(DAEMON_CONNECT_TIMEOUT_S)
            sock.connect(str(SOCKET_PATH))
            sock.sendall(pattern_name.encode("utf-8"))
            sock.settimeout(DAEMON_RESPONSE_TIMEOUT_S)
            response = sock.recv(64).decode("utf-8", "ignore")
        return response == "ok"
    except OSError:
        return None


def _spawn_daemon() -> None:
    subprocess.Popen(
        [sys.executable, str(DAEMON_SCRIPT)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def _rumble_standalone(pattern_name: str) -> bool:
    pulses = RUMBLE_PATTERNS.get(pattern_name, RUMBLE_PATTERNS["default"])
    pygame.joystick.init()
    try:
        hw_map = load_joycon_map()
        joystick = _find_joystick(hw_map.get("device_name_hint", ""))
        if joystick is None:
            return False

        ok = True
        for low, high, duration_ms, gap_after_s in pulses:
            ok = joystick.rumble(low, high, duration_ms) and ok
            time.sleep(duration_ms / 1000)
            joystick.stop_rumble()
            time.sleep(gap_after_s)
        return ok
    finally:
        pygame.joystick.quit()


def rumble(pattern_name: str = "default") -> bool:
    """指定パターンでJoy-Conを振動させる。すべてのパルスを開始できたらTrueを返す。"""
    _log(f"start pattern={pattern_name} pid={os.getpid()}")

    daemon_result = _try_daemon(pattern_name)
    if daemon_result is not None:
        _log(f"end pattern={pattern_name} path=daemon ok={daemon_result}")
        return daemon_result

    ok = _rumble_standalone(pattern_name)
    _log(f"end pattern={pattern_name} path=fallback ok={ok}")
    # joystickを手放した後でデーモンを起動する(振動処理と同時に別プロセスが
    # 同じJoy-Conを掴もうとする競合を避けるため)。次回以降は高速パスになる。
    _spawn_daemon()
    return ok


if __name__ == "__main__":
    rumble(sys.argv[1] if len(sys.argv) > 1 else "default")
