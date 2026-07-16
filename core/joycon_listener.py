"""
Joy-Con(L) 入力検知プログラム (Input Listener)

`pygame` の joystick モジュールでボタン押下・アナログスティックの入力を常時監視し、
config/joycon_map.json のハードウェアマッピングに従って正規化したイベントに変換して
コールバックへ渡す。ボタン名や8方向の意味づけは一切持たず、
「どの論理名のボタン/方向が押された/離された/動いた」だけを通知する薄い層にすることで、
アクション実行側(action_dispatcher)と疎結合にしている。

正規化イベント (callback(event_name, data) で通知される):
  - ("button_down", {"name": "L"})
  - ("button_up",   {"name": "L"})
  - ("stick_move",  {"x": -1.0..1.0, "y": -1.0..1.0})
  - ("device_status", {"connected": bool, "message": str})
"""
from __future__ import annotations

import logging
import math
import time
from collections.abc import Callable
from typing import Any

import pygame

logger = logging.getLogger(__name__)

EventCallback = Callable[[str, dict[str, Any]], None]


class JoyConListener:
    def __init__(self, hw_map: dict[str, Any], callback: EventCallback) -> None:
        self._hw_map = hw_map
        self._callback = callback
        self._joystick: pygame.joystick.JoystickType | None = None
        self._running = False

        # スティックの微弱なズレ・ノイズの無視閾値（oshi_ring側のdeadzoneと同じ値を共有する）
        self._deadzone_axis_noise = hw_map.get("deadzone", 0.5)
        self._stick_x_axis = hw_map["axes"]["stick_x"]
        self._stick_y_axis = hw_map["axes"]["stick_y"]
        self._invert_y = bool(hw_map["axes"].get("invert_y", False))
        self._stick_value = [0.0, 0.0]
        self._last_emitted_stick: tuple[float, float] = (0.0, 0.0)

        # button index -> 論理名 のリスト（複数の論理名が同じ物理ボタンに対応する場合に備えリスト化）
        self._button_index_to_names: dict[int, list[str]] = {}
        # hat index -> [(論理名, axis("x"/"y"), value(+1/-1)), ...]
        self._hat_index_to_entries: dict[int, list[tuple[str, str, int]]] = {}
        self._hat_state: dict[int, tuple[int, int]] = {}
        self._pressed_names: set[str] = set()

        for name, entry in hw_map["buttons"].items():
            if entry["kind"] == "button":
                self._button_index_to_names.setdefault(entry["index"], []).append(name)
            elif entry["kind"] == "hat":
                self._hat_index_to_entries.setdefault(entry["index"], []).append(
                    (name, entry["axis"], entry["value"])
                )

    def _find_joystick(self) -> pygame.joystick.JoystickType | None:
        hint = self._hw_map.get("device_name_hint", "").lower()
        best = None
        for i in range(pygame.joystick.get_count()):
            js = pygame.joystick.Joystick(i)
            js.init()
            if hint and hint in js.get_name().lower():
                return js
            if best is None:
                best = js
        return best

    def _emit(self, name: str, data: dict[str, Any]) -> None:
        try:
            self._callback(name, data)
        except Exception:
            logger.exception("イベントコールバック処理中にエラーが発生しました: %s", name)

    def _connect(self) -> bool:
        pygame.joystick.quit()
        pygame.joystick.init()
        self._joystick = self._find_joystick()
        self._hat_state.clear()
        self._pressed_names.clear()
        self._stick_value = [0.0, 0.0]
        self._last_emitted_stick = (0.0, 0.0)
        if self._joystick is None:
            self._emit("device_status", {"connected": False, "message": "Joy-Conが見つかりません"})
            return False

        self._emit(
            "device_status",
            {"connected": True, "message": f"接続済み: {self._joystick.get_name()}"},
        )
        return True

    def _handle_button(self, index: int, pressed: bool) -> None:
        for name in self._button_index_to_names.get(index, []):
            if pressed and name not in self._pressed_names:
                self._pressed_names.add(name)
                self._emit("button_down", {"name": name})
            elif not pressed and name in self._pressed_names:
                self._pressed_names.discard(name)
                self._emit("button_up", {"name": name})

    def _handle_hat(self, index: int, value: tuple[int, int]) -> None:
        prev = self._hat_state.get(index, (0, 0))
        self._hat_state[index] = value
        for name, axis, target in self._hat_index_to_entries.get(index, []):
            component = value[0] if axis == "x" else value[1]
            prev_component = prev[0] if axis == "x" else prev[1]
            was_pressed = prev_component == target and target != 0
            is_pressed = component == target and target != 0
            if is_pressed and not was_pressed:
                self._pressed_names.add(name)
                self._emit("button_down", {"name": name})
            elif was_pressed and not is_pressed:
                self._pressed_names.discard(name)
                self._emit("button_up", {"name": name})

    def _handle_axis(self, index: int, value: float) -> None:
        if index == self._stick_x_axis:
            self._stick_value[0] = value
        elif index == self._stick_y_axis:
            self._stick_value[1] = -value if self._invert_y else value
        else:
            return

        x, y = self._stick_value
        # 各軸を独立して切り捨てると斜め入力(両軸とも小さめ)が失われるため、
        # 合成の大きさ(magnitude)で判定する。閾値未満のときだけ原点に丸める。
        if math.hypot(x, y) < self._deadzone_axis_noise:
            x = 0.0
            y = 0.0

        if (x, y) == self._last_emitted_stick:
            return
        self._last_emitted_stick = (x, y)
        self._emit("stick_move", {"x": x, "y": y})

    def stop(self) -> None:
        self._running = False

    def run(self, poll_hz: float = 125.0) -> None:
        """常時監視ループ（ブロッキング）。別スレッドから呼び出すことを想定。"""
        pygame.init()
        self._running = True
        interval = 1.0 / poll_hz

        while self._running:
            if self._joystick is None:
                if not self._connect():
                    time.sleep(1.0)
                    continue

            for event in pygame.event.get():
                if event.type == pygame.JOYDEVICEADDED:
                    # _connect()内のjoystick.quit()/init()自体がこのイベントを
                    # 生成することがあるため、ここでは無視する
                    # （未接続時の再接続は self._joystick is None のチェックに任せる）。
                    continue
                if event.type == pygame.JOYDEVICEREMOVED:
                    if (
                        self._joystick is not None
                        and event.instance_id == self._joystick.get_instance_id()
                    ):
                        self._joystick = None
                    continue
                if event.type == pygame.JOYBUTTONDOWN:
                    self._handle_button(event.button, True)
                elif event.type == pygame.JOYBUTTONUP:
                    self._handle_button(event.button, False)
                elif event.type == pygame.JOYHATMOTION:
                    self._handle_hat(event.hat, event.value)
                elif event.type == pygame.JOYAXISMOTION:
                    self._handle_axis(event.axis, event.value)

            time.sleep(interval)
