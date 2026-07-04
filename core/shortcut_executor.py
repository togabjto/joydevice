"""
設定で指定されたキー名のリストを実際のキーボード入力として送出するモジュール。

`pynput` を利用しているため Windows / macOS / Linux(X11) で共通のコードで動作する。
キー名は settings.json の "keys" 配列に格納される文字列で、
下記 SPECIAL_KEYS / MEDIA_KEYS に無いものは 1 文字キーとして扱う。
"""
from __future__ import annotations

import logging
import subprocess
import time

from pynput.keyboard import Controller, Key, KeyCode

logger = logging.getLogger(__name__)

# 間隔ゼロで合成キーイベントを連続送信すると、macOSがイベントを取りこぼして
# 途中までしか入力されないことがあるため、各press/release間に短い間隔を空ける。
_KEY_EVENT_DELAY = 0.02

# 修飾キー・特殊キーの名称 -> pynput.keyboard.Key の属性名 の対応表。
# "cmd" は Windows/Linux では Super(Win)キー、macOS では Command キーとして扱われる。
# OSによっては存在しないキー（例: macOSのinsert/print_screen）もあるため、
# 実際の解決は resolve_key() 内で getattr により安全に行う。
_SPECIAL_KEY_ATTRS: dict[str, str] = {
    "ctrl": "ctrl", "control": "ctrl",
    "shift": "shift",
    "alt": "alt", "option": "alt",
    "cmd": "cmd", "win": "cmd", "super": "cmd",
    "enter": "enter", "return": "enter",
    "esc": "esc", "escape": "esc",
    "tab": "tab",
    "space": "space",
    "backspace": "backspace",
    "delete": "delete",
    "up": "up", "down": "down", "left": "left", "right": "right",
    "home": "home", "end": "end",
    "page_up": "page_up", "page_down": "page_down",
    "caps_lock": "caps_lock",
    "insert": "insert",
    "print_screen": "print_screen",
    **{f"f{i}": f"f{i}" for i in range(1, 21)},
}

# メディア/システムキーの名称 -> pynput.keyboard.Key の属性名 の対応表。
_MEDIA_KEY_ATTRS: dict[str, str] = {
    "media_play_pause": "media_play_pause",
    "media_next": "media_next",
    "media_previous": "media_previous",
    "media_stop": "media_stop",
    "volume_up": "media_volume_up",
    "volume_down": "media_volume_down",
    "volume_mute": "media_volume_mute",
}


def resolve_key(name: str) -> Key | KeyCode | None:
    """キー名の文字列を pynput が扱えるキーオブジェクトへ変換する。"""
    attr = _SPECIAL_KEY_ATTRS.get(name) or _MEDIA_KEY_ATTRS.get(name)
    if attr is not None:
        key = getattr(Key, attr, None)
        if key is None:
            logger.warning("キー '%s' はこの環境ではサポートされていません", name)
        return key

    if len(name) == 1:
        return KeyCode.from_char(name)

    logger.warning("未知のキー名です: '%s'", name)
    return None


class ShortcutExecutor:
    """キー名のリストを同時押しとして実行するクラス。"""

    def __init__(self) -> None:
        self._controller = Controller()

    def execute(self, keys: list[str]) -> None:
        if not keys:
            return

        resolved: list[Key | KeyCode] = []
        for name in keys:
            key = resolve_key(name)
            if key is not None:
                resolved.append(key)

        if not resolved:
            return

        pressed: list[Key | KeyCode] = []
        try:
            for key in resolved:
                self._controller.press(key)
                pressed.append(key)
                time.sleep(_KEY_EVENT_DELAY)
        finally:
            for key in reversed(pressed):
                self._controller.release(key)
                time.sleep(_KEY_EVENT_DELAY)

    def paste_text(self, text: str) -> None:
        """文字列をクリップボード経由で一括入力する（macOS専用）。

        1文字ずつキー送出すると長い文字列で取りこぼしが発生しやすいため、
        クリップボードにセットしてから Cmd+V を送ることで、実際のペーストと
        同じ経路で一度に入力させる。
        """
        if not text:
            return

        try:
            subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)
        except (OSError, subprocess.CalledProcessError):
            logger.exception("クリップボードへのコピーに失敗しました（pbcopyはmacOS専用です）")
            return

        self.execute(["cmd", "v"])
