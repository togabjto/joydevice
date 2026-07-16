#!/usr/bin/env python3
"""
別のプロジェクトでJoy-Con振動hookを有効にするためのセットアップスクリプト。

使い方:
  cd /別プロジェクト/
  python3 /path/to/joydevice/bridge/setup_hook.py

これにより、そのプロジェクトの .claude/settings.local.json に
hook設定が自動追加されます（既存の設定は保持されます）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

JOYDEVICE_BRIDGE = Path(__file__).resolve().parent
JOYDEVICE_ROOT = JOYDEVICE_BRIDGE.parent


def get_hooks() -> list[dict]:
    """Joy-Con振動用のhook設定を返す"""
    return [
        {
            "on": "UserPromptSubmit",
            "run": f"python3 {JOYDEVICE_BRIDGE / 'notify_hook.py'} working",
        },
        {
            "on": "Notification",
            "matcher": "permission_prompt",
            "run": f"python3 {JOYDEVICE_BRIDGE / 'notify_hook.py'} permission_prompt",
        },
        {
            "on": "Notification",
            "matcher": "idle_prompt",
            "run": f"python3 {JOYDEVICE_BRIDGE / 'notify_hook.py'} waiting_input",
        },
        {
            "on": "Stop",
            "run": f"python3 {JOYDEVICE_BRIDGE / 'notify_hook.py'} task_done",
        },
    ]


def setup_hooks_in_project(project_dir: Path = None) -> None:
    """指定プロジェクト（またはカレントディレクトリ）にhook設定を追加"""
    if project_dir is None:
        project_dir = Path.cwd()

    project_dir = project_dir.resolve()
    settings_local = project_dir / ".claude" / "settings.local.json"

    print(f"\n🔧 Setting up Joy-Con vibration hooks in {project_dir.name}/")
    print(f"   Config file: {settings_local}")

    # 既存設定を読み込む
    if settings_local.exists():
        try:
            with open(settings_local, "r", encoding="utf-8") as f:
                config = json.load(f)
            print(f"   Found existing config")
        except json.JSONDecodeError as e:
            print(f"   ❌ Invalid JSON in existing config: {e}")
            sys.exit(1)
    else:
        config = {}
        print(f"   Creating new config")

    # hooks を初期化（既存の hooks を保持）
    existing_hooks = config.get("hooks", [])
    new_hooks = get_hooks()

    # 既存のJoy-Con関連hookを削除（重複を避けるため）
    filtered_hooks = [
        h for h in existing_hooks
        if "notify_hook.py" not in h.get("run", "")
    ]

    # 新しいhooksを追加
    merged_hooks = filtered_hooks + new_hooks
    config["hooks"] = merged_hooks

    # 設定を保存
    settings_local.parent.mkdir(parents=True, exist_ok=True)
    with open(settings_local, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"\n✅ Setup complete!")
    print(f"   {len(new_hooks)} Joy-Con hooks added")
    print(f"   joydevice path: {JOYDEVICE_ROOT}")
    print(f"\n📝 Hook configuration:")
    for i, hook in enumerate(new_hooks, 1):
        print(f"   {i}. {hook['on']}", end="")
        if "matcher" in hook:
            print(f" (matcher: {hook['matcher']})", end="")
        print(f" → {hook['run'].split('/')[-1]}")

    print(f"\n🧪 Testing vibration...")
    from bridge.rumble import rumble
    result = rumble("task_done")
    if result:
        print(f"   ✅ Vibration successful! Joy-Con is ready.")
    else:
        print(f"   ❌ Vibration failed. Check bridge/DEBUGGING.md for troubleshooting.")

    print()


def main() -> None:
    # 別プロジェクトから呼ばれた場合、カレントディレクトリを使う
    # joydeviceプロジェクトから呼ばれた場合は警告を出す
    project_dir = Path.cwd()

    if project_dir == JOYDEVICE_ROOT:
        print("\n⚠️  You're already in the joydevice project.")
        print("   Run this script from the project where you want to enable Joy-Con hooks.")
        print("\n   Usage:")
        print("     cd /another/project")
        print(f"     python3 {Path(__file__).name}")
        sys.exit(1)

    setup_hooks_in_project(project_dir)


if __name__ == "__main__":
    main()
