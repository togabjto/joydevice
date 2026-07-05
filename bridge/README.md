# bridge/ — Claude Codeの状態をJoy-Conの振動に変換する層

Claude Code の hooks から呼び出される「中間管理職」レイヤー。Claude Codeの状態
（作業開始／許可待ち／完了）を検知し、Joy-Con(L)の振動(ランブル)に変換する。

## 構成

- `rumble.py` — 振動の実処理の入口。単体スクリプトとしても (`python3 bridge/rumble.py
  <pattern>`)、モジュール (`from bridge.rumble import rumble`) としても呼べる。
  まず `rumble_daemon.py` (常駐デーモン) にUnixドメインソケット経由で振動を依頼する
  **高速パス**を試し、デーモンが起動していなければ自前で `pygame.joystick` を初期化
  して振動させる**フォールバックパス**に切り替える(その場合は次回以降が高速パスに
  なるよう、振動後にデーモンをバックグラウンド起動しておく)。呼び出しごとに
  `bridge/notify.log` へ開始/終了・使用した経路(`path=daemon`/`path=fallback`)を
  記録する(振動が感じられない時に、hook配線側とハードウェア側のどちらが原因かを
  切り分けるため)。
- `rumble_daemon.py` — Joy-Conのjoystickハンドルを掴んだまま待ち受ける常駐プロセス。
  `pygame.joystick.init()` によるBluetoothデバイス探索(0.5〜0.8秒ほどかかる)を
  プロセス起動時の1回きりにすることで、`rumble.py` からの依頼に対して探索コスト
  なしで即座に振動を開始できる。明示的な起動は不要(`rumble.py`がフォールバック
  パスに落ちた際に自動でバックグラウンド起動する)。
- `rumble_patterns.py` — `rumble.py`(フォールバック時)と`rumble_daemon.py`が共有する
  振動パターン定義。経路によって手触りがずれないよう一本化している。
- `notify_hook.py` — Claude Codeのhookから呼ばれるエントリポイント。振動処理を
  `rumble.py` の子プロセスとしてデタッチ起動し、自分自身は即座に終了する
  (hookの完了待ちで次のツール実行やターン終了が遅延しないようにするため)。

## 振動パターン (`rumble.py` の `RUMBLE_PATTERNS`)

| パターン名          | 用途                     | 手触り        |
| ------------------- | ------------------------ | ------------- |
| `working`           | プロンプト送信時(作業開始) | 弱め・短く1回 |
| `permission_prompt` | 許可待ち                  | 強め・長めに1回 |
| `task_done`         | 応答完了(待ちぼうけ)       | 短く2連       |

## hook配線 (`.claude/settings.local.json`、gitignore対象・このマシン固有)

| Claude Codeイベント | matcher            | 呼ぶパターン         |
| -------------------- | ------------------- | -------------------- |
| `UserPromptSubmit`   | (なし・毎回発火)     | `working`            |
| `Notification`       | `permission_prompt` | `permission_prompt`  |
| `Stop`               | (なし・毎回発火)     | `task_done`          |

`.claude/settings.local.json` はこのマシン固有のhook設定なので `.gitignore` 済み。
別マシンでこの機能を使う場合は、このファイルを作り直す必要がある(このREADMEの表の内容を
`.claude/settings.local.json` に `"hooks"` キーとして書けばよい)。

## 現在の検証状況 (2026-07-05時点)

- ✅ `working` / `task_done` / `permission_prompt`: 単体実行、および実際のClaude Code
  実行中の`UserPromptSubmit`/`Stop`/`Notification`発火のいずれでも振動を確認済み。
  (`permission_prompt`はホームディレクトリへのファイル書き込みで実際の許可ダイアログを
  発生させて確認した。)
- ✅ 常駐デーモン方式による高速化: フォールバック(デーモン未起動)時は約1.5秒
  かかっていたのに対し、デーモン経由では約0.7秒(その大半は振動パターン自体の
  再生時間400〜600ms)まで短縮。「許可待ちになってから振動するまでの体感遅延」が
  問題になったため導入した。

## 既知の制限

- 複数の`rumble.py`呼び出しがほぼ同時に「デーモン未起動」と判定した場合、それぞれが
  デーモンを起動しようとして無害な多重起動(古い方は誰にも接続されないまま
  待ち受け続けるゾンビプロセス)が発生し得る。実害はほぼないが、気になる場合は
  `pkill -f rumble_daemon.py` で全部落として次回呼び出し時に1つだけ立ち上げ直す。

## トラブルシューティング

振動が来ない場合、まず `bridge/notify.log` を確認する(感覚に頼らず発火状況を追える)。
`path=daemon`/`path=fallback` でどちらの経路が使われたかも記録されている。

- ログに何も追記されない → hookそのものが発火していない。`.claude/settings.local.json`の
  場所・イベント名・matcher名・`$CLAUDE_PROJECT_DIR`が正しいか確認する。
- `end pattern=... joystick_not_found` → Joy-ConのBluetooth接続を確認する。
- `start`だけ記録されて`end`が来ない → 振動処理の途中でプロセスが強制終了されている。
  (発生済みの既知バグ: `rumble.py`を単体スクリプトとして実行すると`core`パッケージへの
  パスが通らず`ModuleNotFoundError`で即クラッシュしていた。`rumble.py`冒頭の
  `sys.path.insert(...)`で修正済み)
- 毎回`path=fallback`になり続ける → デーモンが起動に失敗している可能性がある。
  `~/.joycon_rumble.sock` が残っていないか、`ps aux | grep rumble_daemon` でプロセスが
  立っているか確認する。

## 前提

Joy-Con(L)がBluetoothでペア済みで、`config/joycon_map.json`の`device_name_hint`で
見つかること(プロジェクト全体の前提と同じ)。
