"""
設定ファイル(settings.json / joycon_map.json)の読み書きを一元管理するモジュール。

action_dispatcher(常駐プロセス)と web.server(設定UI)の両方がこのモジュール経由で
同じスキーマ・同じファイルにアクセスすることで、スキーマの二重管理を防ぐ。
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
SETTINGS_PATH = CONFIG_DIR / "settings.json"
JOYCON_MAP_PATH = CONFIG_DIR / "joycon_map.json"

# 「ボタン」として個別に設定可能なスロット一覧（表示順を兼ねる）
BUTTON_SLOTS: list[str] = [
    "L",
    "ZL",
    "SL",
    "SR",
    "minus",
    "capture",
    "stick_press",
    "dpad_up",
    "dpad_down",
    "dpad_left",
    "dpad_right",
]

# オキニリング（ZL + スティック8方向）のスロット一覧
RING_DIRECTIONS: list[str] = [
    "up",
    "up_right",
    "right",
    "down_right",
    "down",
    "down_left",
    "left",
    "up_left",
]

EMPTY_ACTION: dict[str, Any] = {"label": "", "keys": [], "text": ""}

# UI表示用の日本語名。Web UIはこの辞書を参照するだけでよく、表示名をJS側にハードコードしない。
DISPLAY_NAMES: dict[str, str] = {
    "L": "L",
    "ZL": "ZL（タップ時）",
    "SL": "SL",
    "SR": "SR",
    "minus": "マイナス (-)",
    "capture": "キャプチャ",
    "stick_press": "スティック押し込み",
    "dpad_up": "十字キー 上",
    "dpad_down": "十字キー 下",
    "dpad_left": "十字キー 左",
    "dpad_right": "十字キー 右",
    "up": "上",
    "up_right": "右上",
    "right": "右",
    "down_right": "右下",
    "down": "下",
    "down_left": "左下",
    "left": "左",
    "up_left": "左上",
}


def _empty_settings() -> dict[str, Any]:
    return {
        "buttons": {slot: dict(EMPTY_ACTION) for slot in BUTTON_SLOTS},
        "oshi_ring": {slot: dict(EMPTY_ACTION) for slot in RING_DIRECTIONS},
    }


class ConfigManager:
    """settings.json の読み込み・保存・変更監視を行うスレッドセーフなラッパー。"""

    def __init__(self, settings_path: Path = SETTINGS_PATH):
        self._path = settings_path
        self._lock = threading.Lock()
        self._mtime: float | None = None
        self._settings: dict[str, Any] = _empty_settings()
        self.reload(force=True)

    def _normalize(self, raw: dict[str, Any]) -> dict[str, Any]:
        """欠けているスロットをデフォルト値で補完し、不明なキーは無視する。"""
        normalized = _empty_settings()
        for section in ("buttons", "oshi_ring"):
            for slot, action in (raw.get(section) or {}).items():
                if slot not in normalized[section]:
                    continue
                if not isinstance(action, dict):
                    continue
                keys = action.get("keys")
                normalized[section][slot] = {
                    "label": str(action.get("label", "")),
                    "keys": list(keys) if isinstance(keys, list) else [],
                    "text": str(action.get("text", "")),
                }
        return normalized

    def reload(self, force: bool = False) -> bool:
        """ファイルが変更されていれば読み直す。読み直した場合 True を返す。"""
        try:
            mtime = self._path.stat().st_mtime
        except FileNotFoundError:
            return False

        if not force and mtime == self._mtime:
            return False

        with self._lock:
            with open(self._path, encoding="utf-8") as f:
                raw = json.load(f)
            self._settings = self._normalize(raw)
            self._mtime = mtime
        return True

    def get_settings(self) -> dict[str, Any]:
        with self._lock:
            # 呼び出し元が誤って書き換えないようディープコピーを返す
            return json.loads(json.dumps(self._settings))

    def save_settings(self, new_settings: dict[str, Any]) -> None:
        normalized = self._normalize(new_settings)
        with self._lock:
            self._settings = normalized
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(normalized, f, ensure_ascii=False, indent=2)
            self._mtime = self._path.stat().st_mtime

    def get_action(self, section: str, slot: str) -> dict[str, Any]:
        with self._lock:
            return dict(self._settings.get(section, {}).get(slot, EMPTY_ACTION))


def load_joycon_map(path: Path = JOYCON_MAP_PATH) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_joycon_map(data: dict[str, Any], path: Path = JOYCON_MAP_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
