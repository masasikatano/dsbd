# マクロ・ETF投資判断ダッシュボード

ETF購入のタイミングと銘柄選定のため、マクロ環境と各市場を表で一覧する静的サイトです。仕様は `[spec.md](spec.md)` です。

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

## テスト

```bash
pip install -r requirements-dev.txt
pytest -q
```

## GitHub Pages

リポジトリ Settings → Pages → **Deploy from a branch** → Branch: `main`、Folder: `/docs`。カスタムドメインは使いません。閲覧制限はありません。

GitHub Actions（`.github/workflows/update.yml`）が平日 21:30 UTC と手動 `workflow_dispatch` で Yahoo Finance（および設定時は FRED）から終値を取り、`latest.json` を `[skip ci]` 付きで `main` に push します。`GITHUB_TOKEN` に `contents: write` が必要です。

TIPS 10年・HY-OAS・MOVE・先進国 10 年・**米CPI（月次）**のフォールバックには [FRED](https://fred.stlouisfed.org/) を使います。日本 CPI は総務省統計局の全国総合（2025年基準 CSV）を一次ソースにします。日本・独・英の 10 年利回りは財務省・Bundesbank・英蘭銀行の日次 CSV を一次ソースにし、欠測時だけ FRED OECD へ落とします。CSI 300・VN-Index・USD/CNH は Yahoo が日次履歴を返さないため [EODHD](https://eodhd.com/) から約1年分を取ります。ローカルは `.env` に `FRED_API_KEY` と `EODHD_API_KEY`（git 対象外）。Actions は同名のリポジトリ secret を渡します。未設定でもジョブは成功し、依存行だけ「データなし」になります。キーを JSON やログに出しません。

欠測しても表の行は残し「データなし」と出します。クレジットスプレッドは HY-OAS（FRED）を出します。FRA-OIS は無料ソースに安定シリーズがないため載せていません。CPI・米失業率・ISM製造業 PMI などの月次マクロ指標は「7 マクロ指標（月次）」セクションに表示し、前月比・前年比を出します。

---



## AI エージェント向けガイドライン

### プロジェクト構造

```
config/instruments.yaml  # 指標定義（id, provider, symbol, 閾値など）
src/
  update.py              # 取得・計算・JSON 出力のオーケストレーション
  compute.py             # 5 指標・派生スプレッド計算
  providers/             # Yahoo, FRED, EODHD, official CSV の共通 Provider 実装
    base.py              # Provider プロトコル / FetchResult
docs/
  index.html             # ダッシュボード UI（メインページ）
  detail.html            # 指標詳細ページ（グラフクリックで遷移）
  common.js              # UI 共通ユーティリティ（index/detail 共有）
  data/latest.json       # 生成済みスナップショット（git 管理）
tests/                   # pytest 単体テスト
```



### 検証コマンド

```bash
# テスト
pytest -q

# ダッシュボードデータ更新
python -m src.update

# ローカル確認
./run_local.sh
```

