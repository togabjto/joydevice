# Joy-Con(L) PC左手デバイス化システム

Nintendo Switch の Joy-Con（左）を、PC用の左手デバイス（ショートカット専用コントローラー）として使うためのシステムです。

## ディレクトリ構成

```
joydevice/
├── main.py                     # 入力検知＋アクション実行のエントリポイント
├── requirements.txt
├── config/
│   ├── settings.json           # ボタン/オキニリングに割り当てたショートカット（Web UIから編集）
│   └── joycon_map.json         # Joy-Conの生ボタン/軸インデックスの対応表（要キャリブレーション）
├── core/
│   ├── config_manager.py       # 設定スキーマの一元管理・読み書き
│   ├── joycon_listener.py      # 入力検知プログラム (pygame)
│   ├── oshi_ring.py            # 「オキニリング」(ZLホールド+スティック8方向) の状態管理
│   ├── action_dispatcher.py    # アクション実行モジュール
│   └── shortcut_executor.py    # pynputによるキー送出（クロスプラットフォーム）
├── web/
│   ├── server.py                # Web UI設定サーバー (Flask)
│   ├── templates/index.html
│   └── static/{css,js}/
└── tools/
    └── calibrate.py             # 実機のボタン/軸インデックスを調べる対話ツール
```

## セットアップ

```bash
pip install -r requirements.txt
```

Joy-Con(L) を Bluetooth でペアリングし、OSがジョイスティックとして認識していることを確認してください。

## 1. キャリブレーション（初回のみ）

OS・ドライバによって pygame が返すボタン/軸のインデックスが異なるため、初回は以下を実行して
`config/joycon_map.json` を生成してください。

```bash
python tools/calibrate.py
```

画面の指示に従って各ボタン・スティックの方向を押し/倒しながら Enter を押していくと、
自動的にマッピングが保存されます。

## 2. 起動

```bash
# 入力検知＋アクション実行のみ
python main.py

# 設定Webサーバーも同時に起動（推奨）
python main.py --web
```

`--web` を付けた場合、ブラウザで `http://127.0.0.1:5000` を開くと設定UIにアクセスできます。
Web UI上での変更は `config/settings.json` に保存され、`main.py` 側は自動的に再読込します
（再起動不要）。

Web UIだけを別プロセスで動かしたい場合は次のように起動できます。

```bash
python -m web.server
```

## 3. オキニリングについて

`ZL` を押している間だけ「オキニリングモード」になり、左スティックを倒した8方向
（上/右上/右/右下/下/左下/左/左上）それぞれに独立したショートカットを割り当てられます。

- `ZL` を押してから一度もスティックを倒さずに離した場合は、`ZL` 単体に割り当てたアクションが実行されます。
- `ZL` を押している間にいずれかの方向へスティックを倒すと、その方向のアクションが実行されます
  （中央へ戻してから別方向へ倒すと、その方向のアクションも発火します）。

## 拡張のしかた

- 新しいキー名を `core/shortcut_executor.py` の `SPECIAL_KEYS` / `MEDIA_KEYS` に追加すれば、
  Web UIのキー記録機能・設定ファイルからそのまま利用できます。
- 新しい入力スロットを増やしたい場合は `core/config_manager.py` の `BUTTON_SLOTS` /
  `RING_DIRECTIONS` / `DISPLAY_NAMES` にエントリを追加し、`config/joycon_map.json` に
  対応するハードウェアマッピングを追加するだけで、Web UI・ディスパッチャ双方に反映されます。
