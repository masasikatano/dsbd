# CPI（消費者物価指数）追加計画書

> 本文書は `spec.md` の補足計画である。
> 目的：ETF購入タイミング・銘柄選定のため、マクロ環境を把握する指標として CPI を追加する。

---

## 1. 背景と目的

CPI は中央銀行の金融政策、金利動向、セクター回転の背景を読む上で必須のマクロ指標。
ただし CPI は **月次** であり、現行の日次終値ベースの指標（前日比・年初来・52週位置・200日乖離・1年ボラ）とは性質が異なるため、専用の表示形式を設ける。

## 2. 追加方針

- CPI は **「マクロ指標（月次）」セクション** として新設し、日次指標セクションとは分離する。
- データ取得は **FRED** を使用。Yahoo Finance には月次 CPI シリーズが存在しないため、現行の Yahoo 中心構成では不可。
- 表示項目は月次指標に適した「最新値 / 前月比 / 前年比 / 発表日」とする。
- 取得失敗時は「データなし」と表示し、行は消さない（`spec.md` の方針と同じ）。

## 3. 追加指標

### 3.1 第一弾（必須級）

| id | 名称 | 国・地域 | FRED series | 単位 | 優先度 |
|----|------|---------|-------------|------|--------|
| us_cpi_yoy | 米CPI 前年比 | 米国 | `CPIAUCSL` | 前年比% | next |
| us_core_cpi_yoy | 米コアCPI 前年比 | 米国 | `CPILFESL` | 前年比% | next |
| jp_cpi_yoy | 日CPI 前年比 | 日本 | `JPNCPIALLMINMEI` | 前年比% | advanced |

### 3.2 第二弾（拡張候補）

| id | 名称 | 国・地域 | FRED series | 単位 | 優先度 |
|----|------|---------|-------------|------|--------|
| eu_cpi_yoy | 欧州CPI 前年比 | ユーロ圏 | `CP0000EZ19M086NEST` | 前年比% | advanced |
| us_ppi_yoy | 米PPI 前年比 | 米国 | `PPIFID` | 前年比% | advanced |

※ 第一弾は実装フェーズで確実に動かす。第二弾は将来拡張候補として計画のみ記載する。

## 4. データ取得

### 4.1 ソース

- `FRED_API_KEY` が無い場合は `fred` プロバイダーが missing を返し、行を「データなし」にする。
- 日本 CPI（`JPNCPIALLMINMEI`）は OECD 経由の月次シリーズ。更新タイミングは米CPIより遅れる場合がある。

### 4.2 計算

FRED から取得した後、以下を算出する。

| 項目 | 定義 |
|------|------|
| 最新値 | 直近の月次値（`latest`） |
| 前月比（%） | `(latest / previous - 1) × 100` |
| 前年比（%） | `(latest / value_12m_ago - 1) × 100` |
| 発表日 | FRED の `date` フィールド（実際のリリース日ではなく、該当月の月末や月中値の日付） |

## 5. 設定ファイル変更

### 5.1 `config/instruments.yaml`

新規セクションを追加する。

```yaml
sections:
  - id: s7
    title: "7 マクロ指標（月次）"
```

新規 instruments を追加する。

```yaml
- id: us_cpi_yoy
  section: s7
  market: 米国
  name: CPI 前年比
  provider: fred
  fred_series: CPIAUCSL
  priority: next
  unit: 前年比%
  note: FRED CPIAUCSL。月次・季調済

- id: us_core_cpi_yoy
  section: s7
  market: 米国
  name: コアCPI 前年比
  provider: fred
  fred_series: CPILFESL
  priority: next
  unit: 前年比%
  note: 食品・エネルギー除く。月次・季調済

- id: jp_cpi_yoy
  section: s7
  market: 日本
  name: CPI 前年比
  provider: fred
  fred_series: JPNCPIALLMINMEI
  priority: advanced
  unit: 前年比%
  note: OECD経由の日本CPI
```

### 5.2 `src/providers/fred.py`

現状はスタブであるが、本計画実装時には以下を実装する。

- `FRED_API_KEY` があれば FRED API を呼び出し、指定 series_id の月次データを取得。
- 最新値・1期前・12期前の値を返す。
- API エラー・キー未設定・データ不足時は `status: missing` を返す。

## 6. UI 変更

### 6.1 `docs/index.html`

- セクション 7「マクロ指標（月次）」を追加。
- 既存の 5 指標テーブルとは別形式を使い、以下の列を持つ。
  - 市場
  - 指標名
  - 最新値
  - 前月比（%）
  - 前年比（%）
  - 発表日
  - 備考
- 色分け：前月比・前年比が正なら緑、負なら赤（`spec.md` の騰落色分けと同じ）。

### 6.2 `docs/detail.html`

- 月次指標用の詳細表示を追加。
- チャートは時系列折れ線グラフ（月次）とする。可能であれば前年比トレンドを表示。

## 7. 計算ロジック変更

### 7.1 `src/compute.py`

- 月次指標用の計算関数を追加。
- 既存の `chg_1d_pct`, `ytd_pct`, `pos_52w_pct`, `dev_200d_pct`, `vol_1y_pct` は CPI には適用しない。
- 新しい出力フィールドを `latest.json` に追加する。

### 7.2 `latest.json` の出力例

```json
{
  "generated_at": "2026-09-01T06:30:00+09:00",
  "source": "fred",
  "items": [
    {
      "id": "us_cpi_yoy",
      "status": "ok",
      "last": 307.12,
      "last_date": "2026-07-01",
      "mom_pct": 0.18,
      "yoy_pct": 2.85,
      "market": "米国",
      "name": "CPI 前年比",
      "unit": "前年比%",
      "note": "FRED CPIAUCSL。月次・季調済"
    }
  ]
}
```

## 8. テスト計画

### 8.1 追加テスト

- `tests/test_providers.py`：FRED プロバイダーのキー未設定時の挙動、正常系のデータ取得と計算。
- `tests/test_compute.py`：月次指標の前月比・前年比計算。
- `tests/test_update.py`：`latest.json` に月次指標が含まれること。

### 8.2 手動確認

- `python -m src.update` を実行し、`docs/data/latest.json` に CPI 行が追加されること。
- `docs/index.html` を開き、セクション 7 が正しく表示されること。
- `FRED_API_KEY` を外した場合、CPI 行が「データなし」になること。

## 9. 実装順序

1. `config/instruments.yaml` にセクション 7 と CPI エントリを追加。
2. `src/providers/fred.py` を本番実装（CPI 用の取得・計算）。
3. `src/compute.py` に月次指標計算を追加。
4. `src/update.py` で `latest.json` に CPI 項目を含める。
5. `docs/index.html` にセクション 7 の表示を追加。
6. `docs/detail.html` に月次指標の詳細表示を追加（任意）。
7. テストを追加・実行。
8. `README.md` / `AGENTS.md` を更新（月次指標セクションの説明）。

## 10. 受け入れ条件

- `FRED_API_KEY` 設定時、米CPI前年比・米コアCPI前年比が `latest.json` に `ok` で含まれる。
- `docs/index.html` に「7 マクロ指標（月次）」セクションが表示される。
- CPI 行は「最新値 / 前月比 / 前年比 / 発表日」を表示する。
- `FRED_API_KEY` 未設定時、CPI 行は「データなし」となり、他の指標取得に影響しない。
- `pytest -q` が全件成功する。

## 11. 注意事項

- CPI は月次指標なので、発表日以外は前回値が表示される。これを UI 備考欄やツールチップで説明する。
- 日本 CPI（OECD 経由）は更新が遅れがちなため、必須行にはしない（priority: advanced）。
- FRED API 連携が現状スタブであるため、CPI 追加は **FRED プロバイダー実装後**に行う。
