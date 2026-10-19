"""
設定で指定されたキー名のリストを実際のキーボード入力として送出するモジュール。

`pynput` を利用しているため Windows / macOS / Linux(X11) で共通のコードで動作する。
キー名は settings.json の "keys" 配列に格納される文字列で、
下記 SPECIAL_KEYS / MEDIA_KEYS に無いものは 1 文字キーとして扱う。
"""
from __future__ import annotations

import logging
import subprocess
import sys
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


def check_macos_accessibility(prompt: bool = True) -> bool | None:
    """macOSでアクセシビリティ権限が付与されているか確認する。

    macOSでは、この権限が無いと pynput が送る合成キー入力を OS が無言で破棄するため、
    「ボタンを押してもキーが送出されない」という原因不明の無反応状態になる。
    起動時にここで検出し、未許可なら明確な案内ログを出す（+許可ダイアログを促す）。

    戻り値: 許可済みなら True、未許可なら False、macOS以外/判定不能なら None。
    """
    if sys.platform != "darwin":
        return None
    try:
        from ApplicationServices import (
            AXIsProcessTrusted,
            AXIsProcessTrustedWithOptions,
            kAXTrustedCheckOptionPrompt,
        )
    except Exception:
        # pyobjc が無い等で判定できない場合は黙ってスキップする。
        return None

    if prompt:
        # 未許可なら「システム設定 > プライバシーとセキュリティ > アクセシビリティ」への
        # 追加を促すOS標準ダイアログを表示させる。
        trusted = bool(
            AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: True})
        )
    else:
        trusted = bool(AXIsProcessTrusted())

    if not trusted:
        logger.warning(
            "macOSのアクセシビリティ権限が付与されていません。"
            "この権限が無いとキー入力が送出されず、ボタンを押しても無反応になります。"
            "「システム設定 > プライバシーとセキュリティ > アクセシビリティ」で、"
            "このプログラムを実行しているアプリ（ターミナル/iTerm/python など）を追加し、"
            "許可した後にプログラムを再起動してください。"
        )
    return trusted


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
        # macOSでは権限不足だと無音で失敗するため、起動時に検出して案内する。
        check_macos_accessibility()

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
