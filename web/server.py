"""
Web UI設定プログラム (Config Server & UI)

ブラウザからJoy-Con(L)の各ボタン・オキニリング(ZL+スティック8方向)に
割り当てるショートカットを設定するためのFlaskサーバー。

設定は core.config_manager 経由で config/settings.json に保存され、
実行中の main.py (ActionDispatcher) はファイルの更新を検知して自動的に再読込する。
"""
from __future__ import annotations

import logging

from flask import Flask, jsonify, render_template, request

from core.config_manager import (
    BUTTON_SLOTS,
    DISPLAY_NAMES,
    RING_DIRECTIONS,
    ConfigManager,
)

logger = logging.getLogger(__name__)

MAX_KEYS_PER_ACTION = 5
MAX_TEXT_LENGTH = 2000


def _validate_settings(payload: dict) -> tuple[dict | None, str | None]:
    if not isinstance(payload, dict):
        return None, "設定データはオブジェクトである必要があります"

    cleaned = {"buttons": {}, "oshi_ring": {}}
    sections = {"buttons": BUTTON_SLOTS, "oshi_ring": RING_DIRECTIONS}

    for section, valid_slots in sections.items():
        raw_section = payload.get(section, {})
        if not isinstance(raw_section, dict):
            return None, f"'{section}' はオブジェクトである必要があります"

        for slot in valid_slots:
            action = raw_section.get(slot, {})
            if not isinstance(action, dict):
                return None, f"'{section}.{slot}' はオブジェクトである必要があります"

            label = action.get("label", "")
            keys = action.get("keys", [])
            text = action.get("text", "")
            if not isinstance(label, str):
                return None, f"'{section}.{slot}.label' は文字列である必要があります"
            if not isinstance(keys, list) or not all(isinstance(k, str) for k in keys):
                return None, f"'{section}.{slot}.keys' は文字列の配列である必要があります"
            if len(keys) > MAX_KEYS_PER_ACTION:
                return None, f"'{section}.{slot}.keys' は最大{MAX_KEYS_PER_ACTION}個までです"
            if not isinstance(text, str):
                return None, f"'{section}.{slot}.text' は文字列である必要があります"
            if len(text) > MAX_TEXT_LENGTH:
                return None, f"'{section}.{slot}.text' は最大{MAX_TEXT_LENGTH}文字までです"

            cleaned[section][slot] = {"label": label[:100], "keys": keys, "text": text}

    return cleaned, None


def create_app() -> Flask:
    app = Flask(__name__)
    config_manager = ConfigManager()

    @app.get("/")
    def index():
        return render_template(
            "index.html",
            button_slots=BUTTON_SLOTS,
            ring_directions=RING_DIRECTIONS,
            display_names=DISPLAY_NAMES,
        )

    @app.get("/api/schema")
    def get_schema():
        return jsonify(
            {
                "button_slots": BUTTON_SLOTS,
                "ring_directions": RING_DIRECTIONS,
                "display_names": DISPLAY_NAMES,
            }
        )

    @app.get("/api/config")
    def get_config():
        config_manager.reload()
        return jsonify(config_manager.get_settings())

    @app.post("/api/config")
    def post_config():
        payload = request.get_json(silent=True)
        cleaned, error = _validate_settings(payload or {})
        if error:
            return jsonify({"ok": False, "error": error}), 400

        config_manager.save_settings(cleaned)
        logger.info("設定を保存しました")
        return jsonify({"ok": True, "settings": cleaned})

    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    create_app().run(host="127.0.0.1", port=5000, debug=True)
