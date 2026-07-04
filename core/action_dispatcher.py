"""
アクション実行モジュール (Action Dispatcher)

joycon_listener が発する正規化イベント(button_down/up, stick_move)を受け取り、
ConfigManager が保持する設定(settings.json)と突き合わせて、対応するショートカット
コマンドを shortcut_executor 経由で実行する。

「オキニリング」機能は oshi_ring.OshiRingState に状態管理を委譲し、
このクラスは「どのボタン/方向にどのアクションを結びつけるか」だけを担当する。
"""
from __future__ import annotations

import logging
from typing import Any

from core.config_manager import ConfigManager
from core.oshi_ring import OshiRingState
from core.shortcut_executor import ShortcutExecutor

logger = logging.getLogger(__name__)

# ZL自体はオキニリングのトリガーとして特別扱いするため、
# 単純な「押したら即発火」ボタンの対象から除外する。
_RING_TRIGGER_BUTTON = "ZL"


class ActionDispatcher:
    def __init__(
        self,
        config_manager: ConfigManager,
        deadzone: float = 0.5,
        executor: ShortcutExecutor | None = None,
    ) -> None:
        self._config = config_manager
        self._executor = executor or ShortcutExecutor()
        self._ring = OshiRingState(
            on_ring_action=self._fire_ring_action,
            on_zl_tap=self._fire_zl_tap,
            deadzone=deadzone,
        )

    def handle_event(self, name: str, data: dict[str, Any]) -> None:
        # Web UIでの変更をポーリングなしで反映するため、イベントの度に軽量チェックする。
        self._config.reload()

        if name == "button_down":
            button = data["name"]
            if button == _RING_TRIGGER_BUTTON:
                self._ring.on_zl_down()
            else:
                self._fire_button_action(button)
        elif name == "button_up":
            if data["name"] == _RING_TRIGGER_BUTTON:
                self._ring.on_zl_up()
        elif name == "stick_move":
            self._ring.on_stick_move(data["x"], data["y"])
        elif name == "device_status":
            logger.info(data.get("message", ""))

    def _fire_button_action(self, slot: str) -> None:
        action = self._config.get_action("buttons", slot)
        self._run(action, context=f"button:{slot}")

    def _fire_zl_tap(self) -> None:
        action = self._config.get_action("buttons", _RING_TRIGGER_BUTTON)
        self._run(action, context="button:ZL(tap)")

    def _fire_ring_action(self, direction: str) -> None:
        action = self._config.get_action("oshi_ring", direction)
        self._run(action, context=f"oshi_ring:{direction}")

    def _run(self, action: dict[str, Any], context: str) -> None:
        text = action.get("text") or ""
        if text:
            logger.debug("実行: %s -> テキスト貼り付け (%s)", context, action.get("label", ""))
            self._executor.paste_text(text)
            return

        keys = action.get("keys") or []
        if not keys:
            return
        logger.debug("実行: %s -> %s (%s)", context, keys, action.get("label", ""))
        self._executor.execute(keys)
