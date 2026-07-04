"""
Joy-Con(L) キャリブレーションツール

pygame が実際に返すボタン/軸/ハットのインデックスはOSやドライバによって異なるため、
このスクリプトを対話的に実行して config/joycon_map.json を環境に合わせて生成する。

使い方:
    python tools/calibrate.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pygame  # noqa: E402

from core.config_manager import JOYCON_MAP_PATH, save_joycon_map  # noqa: E402


def record_digital(joystick: "pygame.joystick.JoystickType", prompt: str) -> dict:
    while True:
        input(f"\n[{prompt}] を押した状態のまま Enter キーを押してください... ")
        pygame.event.pump()

        pressed_buttons = [i for i in range(joystick.get_numbuttons()) if joystick.get_button(i)]
        pressed_hats = []
        for h in range(joystick.get_numhats()):
            hx, hy = joystick.get_hat(h)
            if hx != 0:
                pressed_hats.append((h, "x", 1 if hx > 0 else -1))
            if hy != 0:
                pressed_hats.append((h, "y", 1 if hy > 0 else -1))

        total = len(pressed_buttons) + len(pressed_hats)
        if total == 1:
            if pressed_buttons:
                index = pressed_buttons[0]
                print(f"  -> button index {index} として記録しました")
                return {"kind": "button", "index": index}
            hat_index, axis, value = pressed_hats[0]
            print(f"  -> hat {hat_index} ({axis}={value}) として記録しました")
            return {"kind": "hat", "index": hat_index, "axis": axis, "value": value}
        if total == 0:
            print("  入力が検出されませんでした。押したままEnterを押してください。")
        else:
            print("  複数の入力が検出されました。対象の1つだけを押してやり直してください。")


def record_axis(joystick: "pygame.joystick.JoystickType", direction_label: str) -> tuple[int, int]:
    while True:
        input(f"\nスティックを[{direction_label}]いっぱいに倒した状態のまま Enter キーを押してください... ")
        pygame.event.pump()

        best_index, best_value = None, 0.0
        for i in range(joystick.get_numaxes()):
            value = joystick.get_axis(i)
            if abs(value) > abs(best_value):
                best_index, best_value = i, value

        if best_index is not None and abs(best_value) > 0.5:
            sign = 1 if best_value > 0 else -1
            print(f"  -> axis index {best_index} (value={best_value:.2f}) として記録しました")
            return best_index, sign
        print("  スティックの動きを検出できませんでした。もう一度お試しください。")


def choose_joystick() -> "pygame.joystick.JoystickType":
    count = pygame.joystick.get_count()
    if count == 0:
        raise SystemExit(
            "ジョイスティックが検出されません。Joy-Con(L)をペアリング/接続してから再実行してください。"
        )

    print("検出されたデバイス:")
    joysticks = []
    for i in range(count):
        js = pygame.joystick.Joystick(i)
        js.init()
        joysticks.append(js)
        print(f"  [{i}] {js.get_name()}")

    if count == 1:
        return joysticks[0]

    while True:
        raw = input("使用するデバイス番号を入力してください: ").strip()
        if raw.isdigit() and int(raw) < count:
            return joysticks[int(raw)]
        print("無効な番号です。")


def main() -> None:
    pygame.init()
    pygame.joystick.init()

    joystick = choose_joystick()
    print(f"\n'{joystick.get_name()}' を使ってキャリブレーションを開始します。\n")

    hw_map: dict = {
        "_readme": (
            "calibrate.py によって自動生成されたJoy-Con(L)のハードウェアマッピングです。"
            "接続環境が変わった場合は再実行してください。"
        ),
        "device_name_hint": joystick.get_name(),
        "deadzone": 0.5,
        "axes": {},
        "buttons": {},
    }

    hw_map["buttons"]["L"] = record_digital(joystick, "L ボタン")
    hw_map["buttons"]["ZL"] = record_digital(joystick, "ZL ボタン")
    hw_map["buttons"]["minus"] = record_digital(joystick, "－ (マイナス) ボタン")
    hw_map["buttons"]["capture"] = record_digital(joystick, "キャプチャ ボタン")
    hw_map["buttons"]["stick_press"] = record_digital(joystick, "スティック押し込み")
    hw_map["buttons"]["dpad_up"] = record_digital(joystick, "十字キー 上")
    hw_map["buttons"]["dpad_down"] = record_digital(joystick, "十字キー 下")
    hw_map["buttons"]["dpad_left"] = record_digital(joystick, "十字キー 左")
    hw_map["buttons"]["dpad_right"] = record_digital(joystick, "十字キー 右")

    stick_x_index, _x_sign = record_axis(joystick, "右")
    stick_y_index, y_sign = record_axis(joystick, "上")
    hw_map["axes"] = {
        "stick_x": stick_x_index,
        "stick_y": stick_y_index,
        "invert_y": y_sign < 0,
    }

    save_joycon_map(hw_map)
    print(f"\n設定を保存しました: {JOYCON_MAP_PATH}")
    print("main.py を起動して動作を確認してください。")


if __name__ == "__main__":
    main()
