"""
Claude Codeの状態をJoy-Conに反映させる「中間管理職」レイヤーのエントリポイント。

Claude Codeの各hook(UserPromptSubmit, Notification, Stopなど)から
以下のように呼び出されることを想定している。振動パターン名を引数で受け取り、
どの状態かをフック設定側(イベント名・matcher)で振り分ける。

    python3 bridge/notify_hook.py working
    python3 bridge/notify_hook.py permission_prompt
    python3 bridge/notify_hook.py task_done

Claude Codeはhookプロセスの終了を待つため、振動が終わるまでここで
ブロックすると次のツール実行やターン終了がその分遅れてしまう。
そのため実際の振動はrumble.pyを子プロセスとして切り離して起動し、
このプロセス自体は即座に終了する。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

RUMBLE_SCRIPT = Path(__file__).resolve().parent / "rumble.py"


def main() -> None:
    pattern_name = sys.argv[1] if len(sys.argv) > 1 else "default"
    subprocess.Popen(
        [sys.executable, str(RUMBLE_SCRIPT), pattern_name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


if __name__ == "__main__":
    main()
