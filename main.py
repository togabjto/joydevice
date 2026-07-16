"""
Joy-Con(L) PC左手デバイス化システム — メインエントリポイント

入力検知(JoyConListener)とアクション実行(ActionDispatcher)を起動する。
`--web` オプションを付けると、設定用Webサーバーもバックグラウンドスレッドで
同時に起動する（別プロセスで `python -m web.server` を実行しても良い）。

使用例:
    python main.py               # 入力検知のみを起動
    python main.py --web         # 入力検知 + 設定Webサーバーを同時起動
    python main.py --web --port 8080
    python main.py --debug       # 受信した生イベントもログに出す
"""
from __future__ import annotations

import argparse
import logging
import subprocess
import sys
import threading
from pathlib import Path

from core.action_dispatcher import ActionDispatcher
from core.config_manager import ConfigManager, load_joycon_map
from core.joycon_listener import JoyConListener

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Joy-Con(L) PC左手デバイス化システム")
    parser.add_argument("--web", action="store_true", help="設定Webサーバーも同時に起動する")
    parser.add_argument("--host", default="127.0.0.1", help="Webサーバーのホスト (--web時のみ有効)")
    parser.add_argument("--port", type=int, default=5000, help="Webサーバーのポート (--web時のみ有効)")
    parser.add_argument("--debug", action="store_true", help="デバッグログを有効にする")
    return parser.parse_args()


def start_web_server(host: str, port: int) -> None:
    from werkzeug.serving import make_server

    from web.server import create_app

    app = create_app()
    try:
        # make_server()はコンストラクタ内でソケットをbindするため、
        # ポート競合などの起動失敗をこの時点（メインスレッド）で検知できる。
        server = make_server(host, port, app)
    except OSError as exc:
        raise RuntimeError(
            f"設定Webサーバーを起動できませんでした（http://{host}:{port} は使用中の可能性があります）: {exc}"
        ) from exc

    thread = threading.Thread(target=server.serve_forever, daemon=True, name="web-server")
    thread.start()
    logger.info("設定Webサーバーを起動しました: http://%s:%d", host, port)


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # 振動用デーモンをバックグラウンド起動（高速パス化のため）
    daemon_script = Path(__file__).resolve().parent / "bridge" / "rumble_daemon.py"
    subprocess.Popen(
        [sys.executable, str(daemon_script)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    config_manager = ConfigManager()
    hw_map = load_joycon_map()
    dispatcher = ActionDispatcher(config_manager, deadzone=hw_map.get("deadzone", 0.5))

    def on_event(name: str, data: dict) -> None:
        if args.debug:
            logger.debug("event: %s %s", name, data)
        dispatcher.handle_event(name, data)

    if args.web:
        try:
            start_web_server(args.host, args.port)
        except RuntimeError as exc:
            logger.error("%s", exc)
            return

    listener = JoyConListener(hw_map, on_event)
    logger.info("Joy-Con(L) の入力監視を開始します。終了するには Ctrl+C を押してください。")
    try:
        listener.run()
    except KeyboardInterrupt:
        logger.info("終了します。")
    finally:
        listener.stop()


if __name__ == "__main__":
    main()
