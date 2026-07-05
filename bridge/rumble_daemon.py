"""Joy-Conのjoystickハンドルを掴んだまま待ち受け、振動リクエストに即座に応答する常駐デーモン。

bridge/rumble.py が単体で振動させる場合、毎回 `pygame.joystick.init()` でJoy-Conを
Bluetooth経由で探索し直す必要があり、これだけで0.5〜0.8秒ほどかかる(SDL側のデバイス
列挙が重い)。許可待ち通知のように「今すぐ震えてほしい」用途ではこの遅延が気になるため、
デバイスハンドルを保持したままリクエストを待ち受けるこのデーモンを経由することで、
探索コストをプロセス起動時の1回きりにする。

起動は明示的に行わなくてよい。bridge/rumble.py がソケットへの接続に失敗した時点
(＝デーモン未起動)でこのスクリプトを自動でバックグラウンド起動するので、
2回目以降のリクエストから自然に高速パスへ切り替わる。
"""
from __future__ import annotations

import fcntl
import os
import socket
import sys
import time
from pathlib import Path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pygame

from bridge.rumble_patterns import RUMBLE_PATTERNS, SOCKET_PATH
from core.config_manager import load_joycon_map

LOG_PATH = Path(__file__).resolve().parent / "notify.log"
# 起動しているデーモンを1つに限定するためのロックファイル。notify_hook.py/rumble.py は
# デーモンが応答しないたびに再起動を試みるため、ロック無しだと古いデーモンがソケットの
# パスだけ奪われて誰にも繋がらないまま生き残る「ゾンビ」が積み重なってしまう。
LOCK_PATH = Path.home() / ".joycon_rumble.lock"


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


def _reconnect(hw_map: dict) -> pygame.joystick.JoystickType | None:
    pygame.joystick.quit()
    pygame.joystick.init()
    return _find_joystick(hw_map.get("device_name_hint", ""))


def _send_best_effort(conn: socket.socket, payload: bytes) -> None:
    try:
        conn.sendall(payload)
    except OSError:
        pass


def _pulse(joystick: pygame.joystick.JoystickType, pattern_name: str) -> bool:
    pulses = RUMBLE_PATTERNS.get(pattern_name, RUMBLE_PATTERNS["default"])
    ok = True
    for low, high, duration_ms, gap_after_s in pulses:
        ok = joystick.rumble(low, high, duration_ms) and ok
        time.sleep(duration_ms / 1000)
        joystick.stop_rumble()
        time.sleep(gap_after_s)
    return ok


def _acquire_singleton_lock():
    """他に起動中のデーモンがいればNoneを返す。戻り値のファイルオブジェクトは
    プロセスが終了するまで(またはcloseするまで)保持しておくこと(閉じるとロックが外れる)。"""
    lock_file = open(LOCK_PATH, "w")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        lock_file.close()
        return None
    return lock_file


def main() -> None:
    lock_file = _acquire_singleton_lock()
    if lock_file is None:
        _log(f"daemon pid={os.getpid()} already_running exit")
        return

    hw_map = load_joycon_map()
    pygame.joystick.init()
    joystick = _find_joystick(hw_map.get("device_name_hint", ""))

    if SOCKET_PATH.exists():
        SOCKET_PATH.unlink()
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(SOCKET_PATH))
    server.listen(4)
    _log(f"daemon start pid={os.getpid()} joystick={'found' if joystick else 'not_found'}")

    try:
        while True:
            conn, _addr = server.accept()
            with conn:
                pattern_name = conn.recv(64).decode("utf-8", "ignore").strip()
                if not pattern_name:
                    continue
                if joystick is None:
                    joystick = _reconnect(hw_map)
                if joystick is None:
                    _log(f"daemon pattern={pattern_name} joystick_not_found")
                    _send_best_effort(conn, b"joystick_not_found")
                    continue
                _log(f"daemon pattern={pattern_name} start pid={os.getpid()}")
                try:
                    ok = _pulse(joystick, pattern_name)
                except pygame.error:
                    # 振動中にJoy-Conが切断されるなどした場合、次回リクエストで再接続を試みる
                    joystick = None
                    ok = False
                _log(f"daemon pattern={pattern_name} end ok={ok}")
                # notify_hook.py は応答を待たずに投げっぱなしにするため、相手が既に
                # ソケットを閉じてBrokenPipeErrorになってもデーモン自体は落とさない。
                _send_best_effort(conn, b"ok" if ok else b"fail")
    finally:
        server.close()
        if SOCKET_PATH.exists():
            SOCKET_PATH.unlink()
        pygame.joystick.quit()


if __name__ == "__main__":
    main()
