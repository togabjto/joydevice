"""
Claude Codeの状態をJoy-Conに反映させる「中間管理職」レイヤーのエントリポイント。

Claude Codeの各hook(UserPromptSubmit, Notification, Stopなど)から
以下のように呼び出されることを想定している。振動パターン名を引数で受け取り、
どの状態かをフック設定側(イベント名・matcher)で振り分ける。

    python3 bridge/notify_hook.py working
    python3 bridge/notify_hook.py permission_prompt
    python3 bridge/notify_hook.py task_done

Claude Codeはhookプロセスの終了を待つため、振動が終わるまでここでブロックすると
次のツール実行やターン終了がその分遅れてしまう。そのため:

- 常駐デーモン(rumble_daemon.py)が起動していれば、ここから直接ソケットへ
  パターン名を投げっぱなしにして即座に終了する(応答は待たない。pygameの
  importもしない — 「許可待ちになってから振動するまでワンテンポ遅れる」原因が
  rumble.pyの起動+pygame importというもう1段の子プロセスだったため、
  ここで直接投げることでその段を丸ごと省く)。
- デーモンが起動していない場合のみ、フォールバック一式を持つrumble.pyを
  子プロセスとしてデタッチ起動する(自前初期化しての振動、およびデーモンの
  バックグラウンド起動はそちらに任せる)。
"""
from __future__ import annotations

import socket
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bridge.rumble_patterns import DAEMON_CONNECT_TIMEOUT_S, SOCKET_PATH

RUMBLE_SCRIPT = Path(__file__).resolve().parent / "rumble.py"


def _fire_and_forget_to_daemon(pattern_name: str) -> bool:
    """常駐デーモンへパターン名を投げっぱなしにする。デーモンに繋がったかどうかを返す
    (応答内容は待たない — 振動の成否はデーモン自身がnotify.logに記録する)。"""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(DAEMON_CONNECT_TIMEOUT_S)
            sock.connect(str(SOCKET_PATH))
            sock.sendall(pattern_name.encode("utf-8"))
        return True
    except OSError:
        return False


def main() -> None:
    pattern_name = sys.argv[1] if len(sys.argv) > 1 else "default"
    if _fire_and_forget_to_daemon(pattern_name):
        return

    # デーモンが起動していないので rumble.py を別プロセスで起動。
    # ここは高速パスに乗らなかった（デーモンが未起動）ということなので、
    # rumble.py がフォールバック初期化をしてくれる。
    subprocess.Popen(
        [sys.executable, str(RUMBLE_SCRIPT), pattern_name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


if __name__ == "__main__":
    main()
