# マクロ・ETF投資判断ダッシュボード

ETF購入のタイミングと銘柄選定のため、マクロ環境と各市場を表で一覧する静的サイトです。仕様は [`spec.md`](spec.md) です。

## 動かし方

```bash
./run_local.sh
```

venv 作成、依存インストール、`python -m src.update`、`docs/` の簡易サーバ（既定 8080）まで一気にやります。`docs/data/latest.json` が上書きされます。ブラウザで `http://127.0.0.1:8080/` を開きます。

```bash
./run_local.sh --no-serve    # JSON 更新だけ
./run_local.sh --serve-only  # 既存 JSON を配信するだけ
PORT=9000 ./run_local.sh
```

## GitHub Pages

リポジトリ Settings → Pages → **Deploy from a branch** → Branch: `main`、Folder: `/docs`。カスタムドメインは使いません。閲覧制限はありません。

GitHub Actions（`.github/workflows/update.yml`）が平日 21:30 UTC と手動 `workflow_dispatch` で Yahoo Finance（および設定時は FRED）から終値を取り、`latest.json` を `[skip ci]` 付きで `main` に push します。`GITHUB_TOKEN` に `contents: write` が必要です。

TIPS 10年・HY-OAS・MOVE・先進国 10 年のフォールバックには [FRED](https://fred.stlouisfed.org/) を使います。ローカルは `.env` に `FRED_API_KEY=...`（git 対象外）。Actions はリポジトリ secret `FRED_API_KEY` を渡します。未設定でもジョブは成功し、FRED 依存行だけ「データなし」になります。キーを JSON やログに出しません。

欠測しても表の行は残し「データなし」と出します。意図して埋めないのは FRA-OIS のみ（無料ソースに安定シリーズがないため）。詳細は [`spec_v2.md`](spec_v2.md) です。
