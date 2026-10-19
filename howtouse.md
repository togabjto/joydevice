# 使い方（Web UIの起動）

`web/templates/index.html` は、対応する CSS (`web/static/css/style.css`) と
JS (`web/static/js/app.js`) を含めて Flask サーバーが一括で配信します。

## 起動（ターミナルにコピペするだけ）

### Web UIだけ起動（ブラウザも自動で開く）

```bash
cd /Users/ogino/Documents/Desktop/5semseter/claude/joydevice && pip install -q -r requirements.txt && { (sleep 2; open http://127.0.0.1:5000) & python -m web.server; }
```

### Joy-Con入力検知 + Web UIを同時に起動（ブラウザも自動で開く）

```bash
cd /Users/ogino/Documents/Desktop/5semseter/claude/joydevice && pip install -q -r requirements.txt && { (sleep 3; open http://127.0.0.1:5000) & python main.py --web; }
```

ブラウザが自動で開かない場合は http://127.0.0.1:5000 を開いてください。

## 停止

ターミナルで `Ctrl + C`
