# マクロ・ETF投資判断ダッシュボード 仕様

> 目的：ETF購入のタイミング・銘柄選定のため、マクロ環境と各市場の動向を一目で把握する。
> 公開：GitHub Pages（閲覧制限なし。想定閲覧者は本人のみ）。
> 更新：GitHub Actions で自動。
> **指標の単一の真実は `config/instruments.yaml`。本文書は現行の振る舞いを固定する。**
> `spec_v2.md`（欠測埋め）と `spec_cpi.md`（月次 CPI）は本ファイルに統合した。

---

## 1. ゴールと非目標

### 1.1 ゴール

- 静的サイトとして GitHub Pages でダッシュボードを出す。
- 認証・IP制限・非公開化はしない。
- 平日1日1回、米国クローズ後の終値ベースで指標を更新する。
- セクション 1〜6 を日次5指標の表として載せる。
- セクション 7「マクロ指標（月次）」に米失業率・ISM製造業 PMI・CPI を載せる（最新値 / 前月比 / 前年比 / 発表日）。
- 優先度は行バッジ（`must` / `next` / `advanced`）。折りたたみ・タブにしない。
- 欠測しても行は残し「データなし」と出す。

### 1.2 非目標

- ログイン、GitHub private 必須化、Cloudflare Access 等の閲覧制限
- 分足・リアルタイム・WebSocket
- 売買シグナルの自動判定
- 日次スナップショットの git 履歴保管（`latest.json` 上書きのみ）
- FRA-OIS（無料ソースに安定シリーズがないため **行自体を載せない**）
- 日本上場 ETF をセクション6の全行に広げること（価格取得は `etf_nk225` / `etf_topix` のみ）
- 欧州 CPI・米 PPI（拡張候補。未実装）

### 1.3 過去決定からの変更（統合時）

| 旧（v1 / 計画） | 現行 |
|-----------------|------|
| FRED はスタブ | `FRED_API_KEY` があるとき本番呼び出し |
| スパークライン・詳細チャートなし | 必須カードのスパークラインと `detail.html` |
| 日本上場 ETF はティッカー併記のみ | `1321.T` / `1308.T` で終値を取る |
| FRA-OIS は missing のまま行を残す | 行を出さない |
| MOVE は FRED `MOVEINDEX` | Yahoo `^MOVE` |
| 日本 CPI は FRED OECD | 総務省統計局 CSV（`official`） |

---

## 2. システム構成

```
GitHub Actions (平日 21:30 UTC + 手動)
  → python -m src.update
  → docs/data/latest.json を上書き
  → main へ commit & push（[skip ci]）

GitHub Pages（Settings: Deploy from branch main / /docs）
  → docs/index.html が latest.json を fetch して表を描画
  → グラフクリックで docs/detail.html
```

| パス | 役割 |
|------|------|
| `config/instruments.yaml` | 指標定義（id, セクション, 優先度, provider, symbol, ラベル, 備考, 単位, 閾値） |
| `src/update.py` | 取得・計算・JSON 出力 |
| `src/compute.py` | 日次5指標・派生スプレッド・月次前月比/前年比 |
| `src/providers/yahoo.py` | Yahoo Finance |
| `src/providers/fred.py` | FRED（キー未設定なら missing） |
| `src/providers/eodhd.py` | EODHD（Yahoo が日次履歴を返さない銘柄） |
| `src/providers/official.py` | 財務省・Bundesbank・英蘭銀行・総務省 CPI の CSV |
| `docs/index.html` | ダッシュボード |
| `docs/detail.html` | 指標詳細 |
| `docs/common.js` | UI 共通 |
| `docs/data/latest.json` | 最新スナップショット |
| `.github/workflows/update.yml` | 定期更新 |

Pages 用デプロイ Action は使わない。`GITHUB_TOKEN` に `contents: write` が必要。カスタムドメインは使わない。

ローカル: `./run_local.sh`。`.env` に `FRED_API_KEY` / `EODHD_API_KEY`（git 対象外）。キーを JSON やログに出さない。

---

## 3. データ取得

### 3.1 プロバイダ

各 instrument は `provider: yahoo | fred | eodhd | official | derived`（省略時は `yahoo`）。

| provider | 用途 |
|----------|------|
| `yahoo` | 主戦。`symbol` と任意の `symbol_fallbacks` |
| `fred` | TIPS 10年、HY-OAS、米 CPI / コア CPI。キー無しは missing |
| `eodhd` | CSI 300、VN-Index、USD/CNH（Yahoo が日次履歴を返さない） |
| `official` | 日独英 10 年、日本 CPI、ISM製造業 PMI（HTML表） |
| `derived` | `us_2s10s` / `us_10s30s`。依存先 missing なら自身も missing |

フォールバック（オーケストレータ側。プロバイダは疎結合のまま）:

- `yahoo` / `official` で空、または `stale_after_days` より最新値が古い、かつ `fred_series` がある → FRED
- FRED の最終日付が一次ソースより新しいときだけ採用
- MOVE は Yahoo 一次（FRED `MOVEINDEX` は使わない）

### 3.2 スケジュール

- cron: `30 21 * * 1-5`（UTC）
- `workflow_dispatch` あり
- コミットメッセージに `[skip ci]`
- 履歴窓の目安は約2年（EODHD は約1年）

### 3.3 失敗方針

- ティッカー単位で継続。行の `status`: `ok` | `missing`
- UI は missing を「データなし」。行は消さない
- **全件 missing のときだけ** job を失敗させる
- 部分成功は新しい JSON を push する。キー未設定は該当行 missing でジョブ成功

---

## 4. 計算式

### 4.1 日次指標

終値系列を \(P_t\)（当該市場の営業日）。利回りも同じ扱い。単位列で区別する。

| 項目 | 定義 |
|------|------|
| 最終価格 | 系列の最後の有効終値 \(P_n\) |
| 前日比（%） | \((P_n / P_{n-1} - 1) \times 100\) |
| 年初来（%） | 当年最初の営業日終値 \(P_{y0}\) に対し \((P_n / P_{y0} - 1) \times 100\) |
| 52週位置（%） | \( (P_n - L_{52}) / (H_{52} - L_{52}) \times 100\)。直近252営業日。分母0なら「—」 |
| 200日乖離（%） | \( (P_n / MA_{200} - 1) \times 100\)。200営業日未満なら「—」 |
| 1年ボラ | 直近252営業日の日次対数収益の標準偏差 × \(\sqrt{252}\)。パーセント表示 |

派生:

| id | 計算 |
|----|------|
| `us_2s10s` | 米10年 − 米2年（パーセントポイント） |
| `us_10s30s` | 米30年 − 米10年 |

米10年・30年: Yahoo 値が 20 超なら /10 して％に正規化（`scale_if_gt: 20`）。

表示タイムゾーンは **Asia/Tokyo**。`generated_at` は ISO 8601 + オフセット。

### 4.2 月次指標（`monthly: true`）

日次5指標は適用しない。

| 項目 | 定義 |
|------|------|
| 最新値 | 直近の月次値 |
| 前月比（%） | `(latest / previous - 1) × 100` |
| 前年比（%） | `(latest / value_12m_ago - 1) × 100` |
| 発表日 | 系列の `date`（リリース日ではなく観測月の日付） |

CPI は発表日以外は前回値が残る。備考で説明する。

---

## 5. 色分け

- **騰落（前日比・年初来・200日乖離、月次の前月比・前年比）**: 正＝緑、負＝赤、0＝ニュートラル。符号と数値は残す。
- **52週位置**: 色分けしない。
- **VIX**: \<20 ニュートラル、20–30 黄、≥30 赤。
- **2s10s**: 負（逆転）なら赤。正はニュートラル。
- **MOVE / HY-OAS**: `thresholds.wider_is_red` で拡大＝赤。
- **ISM製造業 PMI**: `thresholds.below_is_red`（50）未満なら赤。

---

## 6. UI

- 言語: 日本語。ダーク寄りの表。ビルドツールなし。
- ヘッダー: タイトル、目的文、最終更新（JST）、欠測件数バナー（`欠測 N 件（行は残し「データなし」表示）`）。
- 必須優先度のカード＋スパークライン。
- セクション 1〜6 は日次5指標テーブル。セクション 7 は月次列（市場、指標名、最新値、前月比、前年比、発表日、備考）。
- 行に優先度バッジ。全部展開。狭い画面は横スクロール可。
- グラフから `detail.html`（日次・月次とも時系列）。
- missing の `error` は画面に出さない。

---

## 7. `latest.json`

ラベル・備考・セクションは生成時に JSON へ埋め込む（Pages が yaml を読めないため）。単一の真実は yaml。

日次行は `chg_1d_pct` / `ytd_pct` / `pos_52w_pct` / `dev_200d_pct` / `vol_1y_pct` と任意の `history`。
月次行は `mom_pct` / `yoy_pct`。`source` は複数プロバイダのため `mixed`。

---

## 8. 指標定義

シンボル変更は yaml のみ直す。`provider` 省略時は `yahoo`。

### 8.1 先進国株価指数（1-1）

| id | 市場 | 指標 | symbol | priority |
|----|------|------|--------|----------|
| sp500 | 米国 | S&P 500 | `^GSPC` | must |
| nasdaq100 | 米国 | NASDAQ 100 | `^NDX` | must |
| russell2000 | 米国 | ラッセル2000 | `^RUT` | next |
| nikkei225 | 日本 | 日経平均株価 | `^N225` | must |
| topix | 日本 | TOPIX | `^TOPX`（fallback `1308.T`, `1306.T`） | must |
| stoxx600 | 欧州 | STOXX Europe 600 | `^STOXX` | next |
| dax | 欧州 | DAX | `^GDAXI` | next |
| cac40 | 欧州 | CAC40 | `^FCHI` | next |
| ftse100 | 欧州（英国） | FTSE 100 | `^FTSE` | next |
| asx200 | その他先進 | S&P/ASX 200 | `^AXJO` | advanced |
| tsx | その他先進 | S&P/TSX | `^GSPTSE` | advanced |
| kospi | その他先進 | KOSPI | `^KS11` | advanced |
| taiex | その他先進 | 台湾加権 | `^TWII` | advanced |

### 8.2 新興国株価指数（1-2）すべて advanced

| id | 市場 | 指標 | 取得 |
|----|------|------|------|
| msci_em | グローバル | MSCI EM | `^MSCIEF`（fallback `EEM`） |
| nifty50 | インド | Nifty 50 | `^NSEI` |
| sse | 中国・本土 | 上海総合 | `000001.SS` |
| csi300 | 中国・本土 | CSI 300 | EODHD `000300.SHG` |
| hsi | 中国・香港 | ハンセン | `^HSI` |
| hstech | 中国・香港 | ハンセンテック | `^HSTECH`（fallback `HSTECH.HI`, `3032.HK`。ETF 代用時は note） |
| bovespa | ブラジル | Bovespa | `^BVSP` |
| ipc | メキシコ | IPC | `^MXX` |
| vnindex | ベトナム | VN-Index | EODHD `VNINDEX.INDX` |
| jci | インドネシア | JCI | `^JKSE` |

SENSEX は出さない。

### 8.3 米国セクター（1-3）priority: next

XLK, XLF, XLE, XLV, XLP, XLU, XLRE, XLB, XLI, XLC, XLY。

### 8.4 先進国金利（2-1）

| id | 内容 | 取得 | priority |
|----|------|------|----------|
| us_2y | 米2年 | Yahoo `^UST2YR` / `2YY=F` | next |
| us_10y | 米10年 | Yahoo `^TNX`（scale） | must |
| us_30y | 米30年 | Yahoo `^TYX`（scale） | advanced |
| us_tips_10y | TIPS 10年実質 | FRED `DFII10`（Yahoo 代用しない） | advanced |
| jp_10y | 日本10年 | 財務省 CSV → FRED `IRLTLT01JPM156N` | advanced |
| de_10y | 独10年 | Bundesbank CSV → FRED `IRLTLT01DEM156N` | advanced |
| uk_10y | 英10年 | 英蘭銀行 IUDMNPY → FRED `IRLTLT01GBM156N` | advanced |

OECD フォールバックが月次でも `ok` にしてよい。計算不能な日次セルは「—」。

### 8.5 イールドカーブ・スプレッド（2-2）

| id | 内容 | provider | priority |
|----|------|----------|----------|
| us_2s10s | 米10年 − 米2年 | derived | next |
| us_10s30s | 米30年 − 米10年 | derived | advanced |
| hy_oas | HY-OAS | FRED `BAMLH0A0HYM2`（単位 bp。HYG 代用しない） | next |

### 8.6 インフレ・商品（3）

WTI `CL=F`、Brent `BZ=F`、天然ガス `NG=F`、金 `GC=F`、銀 `SI=F`、銅 `HG=F`、鉄鉱石 `TIO=F`、大豆 `ZS=F`、小麦 `ZW=F`、トウモロコシ `ZC=F`。

### 8.7 為替（4）

DXY `DX-Y.NYB`（must）、USD/EUR・GBP・AUD、USD/CNH（EODHD `USDCNH.FOREX`）、USD/CNY、USD/JPY（must）、EUR/JPY、CHF/JPY、USD/INR・BRL・KRW・TWD。

### 8.8 センチメント（5）

| id | 指標 | 取得 | priority |
|----|------|------|----------|
| vix | VIX | `^VIX` | must |
| move | MOVE | Yahoo `^MOVE` | advanced |
| btc | BTC | `BTC-USD` | next |
| eth | ETH | `ETH-USD` | next |

### 8.9 主要ETF（6）priority: next

米上場は取得。日本は次の2行だけ Yahoo `.T`。その他の日本コードは `listed_also` 併記のみ。JPX日経400は出さない。指数と ETF は別 id で二重表示してよい。

| 対象 | symbol | 併記 |
|------|--------|------|
| S&P 500 | SPY | VOO, IVV |
| NASDAQ 100 | QQQ | |
| ラッセル2000 | IWM | |
| ダウ | DIA | |
| 日経225 | `1321.T`（fallback `1322.T`） | 1322 |
| TOPIX | `1308.T`（fallback `1306.T`） | 1306 |
| STOXX 600 / ユーロ圏 / 独 / 仏 / 英 | VGK, EZU, EWG, EWQ, EWU | |
| MSCI EM | EEM | VWO |
| インド / 中国本土 / 香港 / ブラジル / ベトナム / 韓国 / 台湾 | INDA, ASHR, FXI, EWZ, VNM, EWY, EWT | FXI に 2801 |
| ACWI / EAFE | ACWI, EFA | EFA に VEA |
| 米国債20年超 / 7-10年 / 1-3年 / HY / IG | TLT, IEF, SHY, HYG, LQD | HYG に JNK |

### 8.10 マクロ指標（月次）（7）

日次セクションと分離。

| id | 名称 | 取得 | priority |
|----|------|------|----------|
| us_unrate | 米失業率 | FRED `UNRATE`（季調済） | next |
| us_ism_mfg | ISM製造業 PMI | 公開時系列HTML（`official` `ism_html`）。FRED `NAPM` は配信停止。50割れは赤 | next |
| us_cpi_yoy | 米CPI 前年比 | FRED `CPIAUCSL`（季調済） | next |
| us_core_cpi_yoy | 米コアCPI 前年比 | FRED `CPILFESL` | next |
| jp_cpi_yoy | 日CPI 前年比 | 総務省 全国総合 2025年基準 CSV。指数から前月比・前年比 | advanced |

拡張候補（未実装）: 欧州CPI `CP0000EZ19M086NEST`、米PPI `PPIFID`。

---

## 9. GitHub Pages / 権限

- public リポジトリ。閲覧制限なし。
- Actions は secret `FRED_API_KEY` / `EODHD_API_KEY` を渡す。未設定でもジョブ成功。
- Pages: Branch `main` / folder `/docs`。

---

## 10. 受け入れ条件

- `docs/index.html` は JSON があれば表を出す。セクション 7 がある。
- 必須行（S&P500, NASDAQ100, 日経, TOPIX, 米10年, DXY, USD/JPY, VIX）が、ソースが生きていれば `ok`。
- FRED キーありなら米失業率・米CPI・米コアCPI・TIPS・HY-OAS が `ok`。ISM製造業 PMI は公式HTMLが取れれば `ok`。
- missing 行が表から消えない。FRA-OIS 行は存在しない。
- 認証画面がない。
- Actions に平日 cron と `workflow_dispatch` がある。
- `pytest -q` が全件成功する。
