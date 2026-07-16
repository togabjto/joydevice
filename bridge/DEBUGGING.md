# デバッグガイド — Joy-Conの振動が来ない場合

## 1. 簡単な診断

```bash
cd /path/to/joydevice
python3 bridge/debug_vibration.py status
```

これでハードウェア・設定・デーモン・ログの全体状況が表示されます。

## 2. パターン別の対処法

### パターンA: ログに何も記録されない

**症状:** `bridge/notify.log` に新しい行が追記されない

**原因:** hookそのものが発火していない

**確認:**
1. `.claude/settings.local.json` が存在するか
2. hook設定が正しく書かれているか
3. イベント名（`UserPromptSubmit`, `Notification`, `Stop`）が正しいか

**修正:**
別のプロジェクトでこの機能を使う場合は、各プロジェクトの`.claude/settings.local.json`に以下を追加：

```json
{
  "hooks": [
    {
      "on": "UserPromptSubmit",
      "run": "python3 /absolute/path/to/joydevice/bridge/notify_hook.py working"
    },
    {
      "on": "Notification",
      "matcher": "permission_prompt",
      "run": "python3 /absolute/path/to/joydevice/bridge/notify_hook.py permission_prompt"
    },
    {
      "on": "Stop",
      "run": "python3 /absolute/path/to/joydevice/bridge/notify_hook.py task_done"
    }
  ]
}
```

⚠️ **重要:** `/absolute/path/to/joydevice` を実際のパスに置き換えてください

### パターンB: ログに `joystick_not_found` がある

**症状:** `end pattern=... joystick_not_found`

**原因:** Joy-ConがBluetoothで接続されていない、または認識されていない

**確認:**
```bash
# Joy-Conが見えるか確認
python3 bridge/debug_vibration.py status
```

**修正:**
1. Joy-Con(L)がBluetoothでペアリングされているか確認
2. OSがジョイスティックとして認識しているか確認
3. `config/joycon_map.json` が存在し、`device_name_hint` が正しいか確認

```bash
# デバイスを再スキャン（キャリブレーション）
python3 tools/calibrate.py
```

### パターンC: 毎回 `path=fallback` で遅い

**症状:** `path=fallback` が続く、振動までに1秒以上かかる

**原因:** デーモンが起動していない

**確認:**
```bash
python3 bridge/debug_vibration.py daemon-info
ps aux | grep rumble_daemon
```

**修正:**
手動でデーモンを起動：

```bash
python3 bridge/rumble_daemon.py &
```

または、次の振動リクエストで自動起動します：

```bash
python3 bridge/debug_vibration.py test working
```

### パターンD: `already_running` が複数出ている

**症状:** ログに `daemon pid=... already_running exit` が複数行ある

**原因:** 複数のデーモンが同時に起動しようとした（複数ターミナルで同時にhookが発火）

**修正:**
既知の問題ですが、最新版では自動で解消されます。手動でリセット：

```bash
pkill -f rumble_daemon.py
rm -f ~/.joycon_rumble.lock ~/.joycon_rumble.sock
```

次の振動リクエストで新しいデーモンが起動します。

## 3. 別プロジェクトで振動しない場合

### 原因

Claude Codeのhookは各プロジェクトディレクトリの`.claude/settings.local.json`から読まれます。
別プロジェクトでこの機能を使うには、そのプロジェクトのhook設定が必要です。

### 解決方法

**方法1: マシン全体の設定に追加（推奨）**

`~/.claude/settings.json` を編集して、グローバルhookを設定：

```json
{
  "hooks": [
    {
      "on": "UserPromptSubmit",
      "run": "python3 /path/to/joydevice/bridge/notify_hook.py working"
    },
    {
      "on": "Notification",
      "matcher": "permission_prompt",
      "run": "python3 /path/to/joydevice/bridge/notify_hook.py permission_prompt"
    },
    {
      "on": "Stop",
      "run": "python3 /path/to/joydevice/bridge/notify_hook.py task_done"
    }
  ]
}
```

**方法2: 各プロジェクトで個別に設定**

各プロジェクトの`.claude/settings.local.json`（gitignore）に上記と同じ内容を追加。

### 動作確認

```bash
# デーモンがすでに起動しているなら、即座に（0.1秒以内）振動するはず
cd /別プロジェクト/
python3 /path/to/joydevice/bridge/notify_hook.py working

# ログを確認
tail -f /path/to/joydevice/bridge/notify.log
```

## 4. ログをリアルタイムで監視

振動テスト中にログを監視したい場合：

```bash
# ターミナル1
python3 bridge/debug_vibration.py watch

# ターミナル2（別ウィンドウ）
python3 bridge/debug_vibration.py test permission_prompt
```

## 5. 詳細なトラブルシューティング

### デーモンプロセスを確認

```bash
ps aux | grep rumble
```

複数立っていたら、全部落とす：

```bash
pkill -f rumble_daemon.py
pkill -f rumble.py
```

### ソケットファイルを確認

```bash
ls -la ~/.joycon_rumble.sock
```

デーモンが起動しているなら存在するはず。なければデーモン未起動。

### ロックファイルを確認

```bash
ls -la ~/.joycon_rumble.lock
```

ロック機構が正常に機能しているかを確認。

### config_manager の パス確認

rumble.py から見えている`joycon_map.json`のパス：

```bash
python3 -c "from core.config_manager import JOYCON_MAP_PATH; print(JOYCON_MAP_PATH)"
```

これが予期したパスか確認（joydeviceプロジェクト直下の`config/joycon_map.json`のはず）。

## 6. よくある質問

**Q: 複数ターミナルで作業してるとき、片方の振動が来ない**

A: 同時に複数のhookが発火すると、古いデーモンがゾンビプロセスになることがあります。
その場合、以下でリセット：

```bash
pkill -f rumble_daemon.py
```

次の振動で新しいデーモンが起動します。

**Q: joydeviceプロジェクト以外でも振動させたい**

A: グローバルhookを設定してください（上の「別プロジェクトで振動しない場合」を参照）。
または、各プロジェクトで`.claude/settings.local.json`にhook設定を追加。

**Q: 振動の強さ・パターンを変えたい**

A: `bridge/rumble_patterns.py` を編集。

**Q: デバッグログをもっと詳しく見たい**

A: `bridge/notify.log` は自動追記されます。
`python3 bridge/debug_vibration.py watch` でリアルタイム監視できます。

## 7. テスト用コマンド

### 全パターンをテスト

```bash
python3 bridge/debug_vibration.py test working
python3 bridge/debug_vibration.py test permission_prompt
python3 bridge/debug_vibration.py test task_done
```

### デーモンを明示的に起動

```bash
python3 bridge/rumble_daemon.py &
```

### デーモンを明示的に停止

```bash
pkill -f rumble_daemon.py
rm -f ~/.joycon_rumble.lock ~/.joycon_rumble.sock
```

### ログをクリア

```bash
rm bridge/notify.log
```

（新しい振動リクエストでログが再作成されます）
