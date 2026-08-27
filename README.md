# マクロ・ETF投資判断ダッシュボード

ETF購入のタイミングと銘柄選定のため、マクロ環境と各市場を表で一覧する静的サイトです。仕様は [`spec.md`](spec.md) です。

## 動かし方

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m src.update
```

`docs/data/latest.json` が上書きされます。`docs/index.html` をブラウザで開くか、簡易サーバで確認します。

```bash
python -m http.server -d docs 8080
```

## GitHub Pages

リポジトリ Settings → Pages → **Deploy from a branch** → Branch: `main`、Folder: `/docs`。カスタムドメインは使いません。閲覧制限はありません。

GitHub Actions（`.github/workflows/update.yml`）が平日 21:30 UTC と手動 `workflow_dispatch` で Yahoo Finance から終値を取り、`latest.json` を `[skip ci]` 付きで `main` に push します。`GITHUB_TOKEN` に `contents: write` が必要です。
