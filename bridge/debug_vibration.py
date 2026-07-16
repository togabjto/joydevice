#!/usr/bin/env python3
"""
振動が来ないときのデバッグスクリプト。

使い方:
  # デーモンと設定の状態を確認
  python3 bridge/debug_vibration.py status

  # 簡単な振動テスト（デーモン経由）
  python3 bridge/debug_vibration.py test working

  # ログをリアルタイム監視（別ウィンドウで実行）
  python3 bridge/debug_vibration.py watch

  # デーモンの詳細情報
  python3 bridge/debug_vibration.py daemon-info

  # joycon_map.json の検証
  python3 bridge/debug_vibration.py validate-config
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bridge.rumble_patterns import DAEMON_CONNECT_TIMEOUT_S, SOCKET_PATH
from core.config_manager import JOYCON_MAP_PATH

LOG_PATH = Path(__file__).resolve().parent / "notify.log"


def check_daemon_status() -> bool:
    """デーモンが起動しているかをチェック"""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(DAEMON_CONNECT_TIMEOUT_S)
            sock.connect(str(SOCKET_PATH))
            return True
    except OSError:
        return False


def check_joycon_map() -> tuple[bool, str]:
    """joycon_map.json が読めるかをチェック"""
    try:
        with open(JOYCON_MAP_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return True, f"✅ Found: {JOYCON_MAP_PATH}"
    except FileNotFoundError:
        return False, f"❌ Missing: {JOYCON_MAP_PATH}\n   Need to run: python3 tools/calibrate.py"
    except json.JSONDecodeError as e:
        return False, f"❌ Invalid JSON in {JOYCON_MAP_PATH}: {e}"


def test_vibration(pattern: str = "working") -> None:
    """振動テストを実行"""
    print(f"\n🔊 Testing vibration pattern: {pattern}")
    print(f"   Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   CWD: {os.getcwd()}")

    # ログ開始前の行数を記録
    initial_lines = LOG_PATH.read_text(encoding="utf-8").count("\n") if LOG_PATH.exists() else 0

    # rumble.py を呼ぶ
    from bridge.rumble import rumble
    result = rumble(pattern)

    time.sleep(0.5)

    # 新しいログ行をチェック
    if LOG_PATH.exists():
        log_lines = LOG_PATH.read_text(encoding="utf-8").split("\n")
        new_lines = log_lines[initial_lines:]
        if new_lines and new_lines[0]:
            print(f"\n📝 Log entries:")
            for line in new_lines:
                if line.strip():
                    print(f"   {line}")

    print(f"\n   Result: {'✅ Success' if result else '❌ Failed'}")


def show_status() -> None:
    """全体的な状態を表示"""
    print("\n" + "=" * 60)
    print("JOY-CON VIBRATION DEBUG STATUS")
    print("=" * 60)

    # 1. ジョイスティックの状態
    print("\n[1] Hardware Detection")
    import pygame
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    pygame.joystick.init()
    js_count = pygame.joystick.get_count()
    print(f"    Joysticks detected: {js_count}")
    for i in range(js_count):
        js = pygame.joystick.Joystick(i)
        js.init()
        print(f"      [{i}] {js.get_name()}")
    pygame.joystick.quit()

    # 2. 設定ファイルの状態
    print("\n[2] Configuration Files")
    config_ok, config_msg = check_joycon_map()
    print(f"    {config_msg}")

    if config_ok:
        with open(JOYCON_MAP_PATH, "r", encoding="utf-8") as f:
            joycon_map = json.load(f)
        hint = joycon_map.get("device_name_hint", "(not set)")
        print(f"    Device name hint: {hint}")

    # 3. デーモンの状態
    print("\n[3] Daemon Status")
    daemon_running = check_daemon_status()
    if daemon_running:
        print(f"    ✅ Daemon is running")
        print(f"    Socket: {SOCKET_PATH}")
    else:
        print(f"    ❌ Daemon is not running")
        print(f"    Will start on first rumble call")

    # 4. ログファイルの状態
    print("\n[4] Log File")
    if LOG_PATH.exists():
        stats = LOG_PATH.stat()
        mtime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stats.st_mtime))
        lines = LOG_PATH.read_text(encoding="utf-8").count("\n")
        print(f"    Path: {LOG_PATH}")
        print(f"    Size: {stats.st_size} bytes")
        print(f"    Lines: {lines}")
        print(f"    Last modified: {mtime}")

        # 最後の5行を表示
        last_lines = LOG_PATH.read_text(encoding="utf-8").split("\n")[-6:-1]
        print(f"    Recent entries:")
        for line in last_lines:
            if line.strip():
                print(f"      {line}")
    else:
        print(f"    ❌ Log file not found yet (will be created on first vibration)")

    # 5. ハード ウェア ロック
    print("\n[5] Hardware Lock")
    lock_path = Path.home() / ".joycon_rumble.lock"
    if lock_path.exists():
        print(f"    Lock file exists: {lock_path}")
    else:
        print(f"    No lock file")

    # 6. ソケット
    print("\n[6] Unix Socket")
    if SOCKET_PATH.exists():
        print(f"    Socket exists: {SOCKET_PATH}")
    else:
        print(f"    No socket file (normal if daemon not running)")

    print("\n" + "=" * 60)


def watch_log() -> None:
    """ログをリアルタイム監視"""
    print(f"📝 Watching {LOG_PATH}...")
    print("(Press Ctrl+C to stop)\n")

    last_pos = 0
    while True:
        try:
            if LOG_PATH.exists():
                with open(LOG_PATH, "r", encoding="utf-8") as f:
                    f.seek(last_pos)
                    for line in f:
                        print(line.rstrip())
                    last_pos = f.tell()
            time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n👋 Stopped watching")
            break


def daemon_info() -> None:
    """デーモンプロセスの情報を表示"""
    print("\n🔍 Looking for rumble_daemon processes...\n")

    try:
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True,
            timeout=5
        )

        daemon_lines = [
            line for line in result.stdout.split("\n")
            if "rumble_daemon" in line and "grep" not in line
        ]

        if daemon_lines:
            print(f"Found {len(daemon_lines)} daemon process(es):\n")
            for line in daemon_lines:
                print(f"  {line}")
        else:
            print("No daemon processes running")
    except Exception as e:
        print(f"Error checking processes: {e}")

    # ロックファイルの確認
    lock_path = Path.home() / ".joycon_rumble.lock"
    print(f"\nLock file status:")
    if lock_path.exists():
        print(f"  Exists: {lock_path}")
        try:
            with open(lock_path, "r") as f:
                content = f.read()
                print(f"  Content: {content if content else '(empty)'}")
        except Exception as e:
            print(f"  Error reading: {e}")
    else:
        print(f"  Does not exist (OK if no daemon running)")


def validate_config() -> None:
    """joycon_map.json の検証"""
    print("\n🔧 Configuration Validation\n")

    config_ok, config_msg = check_joycon_map()
    print(config_msg)

    if not config_ok:
        print("\n❌ Cannot proceed without valid joycon_map.json")
        return

    with open(JOYCON_MAP_PATH, "r", encoding="utf-8") as f:
        joycon_map = json.load(f)

    print("\nConfiguration contents:")
    print(json.dumps(joycon_map, ensure_ascii=False, indent=2))

    # Buttonのマッピングを検証
    required_keys = [
        "device_name_hint", "button_indices", "axis_indices",
        "analog_threshold"
    ]
    missing = [k for k in required_keys if k not in joycon_map]

    if missing:
        print(f"\n⚠️  Missing keys: {missing}")
    else:
        print(f"\n✅ All required keys present")


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]

    if command == "status":
        show_status()
    elif command == "test":
        pattern = sys.argv[2] if len(sys.argv) > 2 else "working"
        test_vibration(pattern)
    elif command == "watch":
        watch_log()
    elif command == "daemon-info":
        daemon_info()
    elif command == "validate-config":
        validate_config()
    else:
        print(f"Unknown command: {command}\n")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
