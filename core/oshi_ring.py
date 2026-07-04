"""
「オキニリング」機能の状態管理。

ZLボタンがホールドされている間だけ、Lスティックを倒した8方向を判定し、
方向ごとに独立したアクションを発火させる。

挙動:
- ZLを押している間にスティックを倒しても、その場では発火しない。
  スティックを中央に戻す（またはZLを離す）と、直前まで倒していた方向のアクションが1回発火する
  （倒す方向を切り替えても、最後に倒していた方向だけが対象になる）。
- ZLを押してから、一度もリングの方向を発火させずにZLを離した場合は「タップ」とみなし、
  通常のZL単体アクション（ZLボタン自体に割り当てたショートカット）を発火する。
  リングを1回でも使った場合は、離したときの誤爆を防ぐためZL単体アクションは発火しない。
"""
from __future__ import annotations

import math
from collections.abc import Callable

# 8方向の名前。config_manager.RING_DIRECTIONS と対応させること。
_DIRECTIONS = [
    "right", "up_right", "up", "up_left",
    "left", "down_left", "down", "down_right",
]


def angle_to_direction(x: float, y: float) -> str | None:
    """スティック座標(x: 右+, y: 上+)を8方向名に変換する。原点付近はNoneを返す。"""
    if x == 0 and y == 0:
        return None
    angle = math.degrees(math.atan2(y, x)) % 360
    index = round(angle / 45) % 8
    return _DIRECTIONS[index]


class OshiRingState:
    def __init__(
        self,
        on_ring_action: Callable[[str], None],
        on_zl_tap: Callable[[], None],
        deadzone: float = 0.5,
    ) -> None:
        self._on_ring_action = on_ring_action
        self._on_zl_tap = on_zl_tap
        self._deadzone = deadzone
        self._active = False
        self._ring_used = False
        self._current_direction: str | None = None

    @property
    def is_active(self) -> bool:
        return self._active

    def on_zl_down(self) -> None:
        self._active = True
        self._ring_used = False
        self._current_direction = None

    def on_zl_up(self) -> None:
        if self._active:
            if self._current_direction is not None:
                self._ring_used = True
                self._on_ring_action(self._current_direction)
            elif not self._ring_used:
                self._on_zl_tap()
        self._active = False
        self._current_direction = None

    def on_stick_move(self, x: float, y: float) -> None:
        if not self._active:
            return

        magnitude = math.hypot(x, y)
        direction = angle_to_direction(x, y) if magnitude >= self._deadzone else None

        if direction == self._current_direction:
            return

        previous_direction = self._current_direction
        self._current_direction = direction
        if direction is None and previous_direction is not None:
            self._ring_used = True
            self._on_ring_action(previous_direction)
