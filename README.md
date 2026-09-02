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

## テスト

```bash
pip install -r requirements-dev.txt
pytest -q
```

## GitHub Pages

リポジトリ Settings → Pages → **Deploy from a branch** → Branch: `main`、Folder: `/docs`。カスタムドメインは使いません。閲覧制限はありません。

GitHub Actions（`.github/workflows/update.yml`）が平日 21:30 UTC と手動 `workflow_dispatch` で Yahoo Finance（および設定時は FRED）から終値を取り、`latest.json` を `[skip ci]` 付きで `main` に push します。`GITHUB_TOKEN` に `contents: write` が必要です。

TIPS 10年・HY-OAS・MOVE・先進国 10 年・**CPI（月次）**のフォールバックには [FRED](https://fred.stlouisfed.org/) を使います。CSI 300・VN-Index・USD/CNH は Yahoo が日次履歴を返さないため [EODHD](https://eodhd.com/) から約1年分を取ります。ローカルは `.env` に `FRED_API_KEY` と `EODHD_API_KEY`（git 対象外）。Actions は同名のリポジトリ secret を渡します。未設定でもジョブは成功し、依存行だけ「データなし」になります。キーを JSON やログに出しません。

欠測しても表の行は残し「データなし」と出します。クレジットスプレッドは HY-OAS（FRED）を出します。FRA-OIS は無料ソースに安定シリーズがないため載せていません。CPI などの月次マクロ指標は「7 マクロ指標（月次）」セクションに表示し、前月比・前年比を出します。

---

## AI エージェント向けガイドライン

> **原則: 本プロジェクトのコーディングは Kimi Code のみが行う。**
> Claude、Antigravity、その他の AI エージェントは、コード変更を行わない。読み取り、質問、レビュー、提案は可能。

### 役割分担

| エージェント | 許可される行為 | 禁止事項 |
|-------------|--------------|---------|
| Kimi Code | 設計、実装、テスト、リファクタリング、ドキュメント更新 | なし |
| Claude / Antigravity / その他 | コードの読み取り、質問への回答、レビューコメント、設計提案 | ファイル編集、コミット、プッシュ、ブランチ操作、依存追加 |

### プロジェクト構造

```
config/instruments.yaml  # 指標定義（id, provider, symbol, 閾値など）
src/
  update.py              # 取得・計算・JSON 出力のオーケストレーション
  compute.py             # 5 指標・派生スプレッド計算
  providers/             # Yahoo, FRED, EODHD の共通 Provider 実装
    base.py              # Provider プロトコル / FetchResult
docs/
  index.html             # ダッシュボード UI（メインページ）
  detail.html            # 指標詳細ページ（グラフクリックで遷移）
  common.js              # UI 共通ユーティリティ（index/detail 共有）
  data/latest.json       # 生成済みスナップショット（git 管理）
tests/                   # pytest 単体テスト
```

### コーディングを依頼された場合

コード変更が必要な依頼を受けたら、**必ずユーザーに「Kimi Code に任せてください」と伝え、自身は編集しない**。理由:

- 複数エージェントが同時に編集すると設定・方針が分断される。
- `spec.md` / `spec_v2.md` で固定された仕様を逸脱するリスクがある。
- テスト (`pytest -q`) と `python -m src.update` は必須の検証である。

### 読み取り・レビュー時の注意

- `config/instruments.yaml` は単一の真実源として扱う。
- `src/providers/base.py` の `Provider` / `FetchResult` / `ErrorCode` を参照し、各プロバイダが共通インタフェースに従っているか確認する。
- 新しいデータソースを追加したい場合は、まず `src/providers/base.py` の拡張を検討し、Kimi Code に提案する。
- UI (`docs/index.html`, `docs/detail.html`, `docs/common.js`) はビルドツールなし。CSS/JS を追加する場合も Kimi Code が対応する。

### 検証コマンド

```bash
# テスト
pytest -q

# ダッシュボードデータ更新
python -m src.update

# ローカル確認
./run_local.sh
```
