# マクロ・ETF投資判断ダッシュボード 仕様

> 目的：ETF購入のタイミング・銘柄選定のため、マクロ環境と各市場の動向を一目で把握する。  
> 公開：GitHub Pages（閲覧制限なし。想定閲覧者は本人のみ）。  
> 更新：GitHub Actions で自動。  
> **本文書は grilling の結果を固定した仕様である。実装はこの spec に従う。**

---

## 0. grilling 記録（決定）

質問は1つずつ行い、推奨案付きで確認した。

| # | 質問 | 決定 |
|---|------|------|
| 1 | 市場データの取得先 | **Yahoo Finance（`yfinance`）主戦** |
| 2 | MOVE / FRA-OIS / HY-OAS / TIPS / 鉄鉱石など欠測しやすい指標 | **FRED を後から足せる差し込み口だけ残し、v1 は Yahoo のみ** |
| 3 | Actions の更新頻度 | **平日・米国市場クローズ後 1日1回**（UTC 21:30 目安） |
| 4 | Pages への載せ方 | **`main` に JSON + 生成 HTML をコミットして公開** |
| 5 | フロント実装 | **単一 HTML + CSS + 少量 JS**（ビルドなし） |
| 6 | セクション8の優先度のUI反映 | **全部常時表示。見出しに優先度ラベルのみ** |
| 7 | 各指標の表示項目 | **前日比・年初来・52週位置・200日乖離・1年ボラの5つ** |
| 8 | 色分け | **騰落は緑/赤。閾値付き指標は段階色** |
| 9 | 「前日比」とタイムゾーン | **各市場の直近営業日終値同士。表示は JST** |
| 10 | セクション6のETF（米/日上場） | **米上場は数値取得。日本上場はティッカー併記のみ** |
| 11 | v1 の指標カバレッジ | **リスト全件を Yahoo で試行。失敗行は「データなし」** |
| 12 | 共通理解のあと何をするか | **`spec.md` だけ先に書く。実装は止める** |

補足（推奨として仕様に含めるが、独立した質問では選ばせていないもの）:

- schedule に加えて `workflow_dispatch` を付ける。
- 日次履歴 JSON はコミットしない（`latest.json` 上書きのみ）。リポジトリ肥大化防止。

---

## 1. ゴールと非目標

### 1.1 ゴール

- 静的サイトとして GitHub Pages でダッシュボードを出す。
- 認証・IP制限・非公開化はしない。
- 平日1日1回、米国クローズ後の終値ベースで指標を更新する。
- 元のダッシュボード草案のセクション 1〜6 を表としてすべて載せる。
- セクション7の5指標を各行に出す（計算不能なら「—」）。
- セクション8の優先度はバッジで示す（折りたたみ・タブにしない）。

### 1.2 非目標（v1）

- ログイン、GitHub private 必須化、Cloudflare Access 等の閲覧制限
- 分足・リアルタイム・WebSocket
- スパークライン・履歴チャート
- 売買シグナルの自動判定
- FRED API の本番接続
- 日本上場 ETF の価格取得
- 日次スナップショットの git 履歴保管

---

## 2. システム構成

```
GitHub Actions (平日 21:30 UTC + 手動)
  → Python 3.12 + yfinance + pandas
  → config の全銘柄を取得・計算
  → docs/data/latest.json を上書き
  → main へ commit & push（[skip ci]）

GitHub Pages（Settings: Deploy from branch main / /docs）
  → docs/index.html が latest.json を fetch して表を描画
```

| パス | 役割 |
|------|------|
| `config/instruments.yaml` | 指標定義（id, セクション, 優先度, provider, symbol, ラベル, 備考, 単位, 閾値） |
| `src/providers/yahoo.py` | Yahoo 取得 |
| `src/providers/fred.py` | **スタブ**。未設定・未実装ならスキップし、行は missing |
| `src/compute.py` | 5指標と派生スプレッドの計算 |
| `docs/index.html` | UI（単一ファイル。CSS/JS は同一ファイルまたは `docs/` 内の静的ファイル） |
| `docs/data/latest.json` | 最新スナップショット |
| `.github/workflows/update.yml` | 定期更新 |

Pages 用デプロイ Action は使わない。リポジトリ設定で `main` の `/docs` を公開する。README に設定手順を1段落書く（実装時）。

---

## 3. データ取得

### 3.1 プロバイダ

- v1 の実取得は `yahoo` のみ。
- 各 instrument に `provider: yahoo | fred | derived` を持つ。
- `fred` は v1 では呼ばない（または呼んでも即 missing）。後で API キーとシリーズ ID を足せる形にする。
- `derived` は他行の値から計算する（2s10s, 10s30s）。依存先が missing なら自身も missing。

### 3.2 スケジュール

- cron: `30 21 * * 1-5`（UTC）。米国通常取引終了（16:00 ET）のあと。夏時間でも終了後になる側に寄せる。
- `workflow_dispatch` あり。
- コミットメッセージに `[skip ci]` を含め、JSON コミットで workflow が再起動しないようにする。

### 3.3 失敗方針

- ティッカー単位で try/except。ログして継続。
- 行の `status`: `ok` | `missing`。
- UI は missing を「データなし」と表示し、行は消さない。
- **全件 missing のときだけ** job を失敗させる。
- Yahoo の一時障害で前日 JSON を残すかはそのジョブがコミットしなければ自然に残る（失敗時は push しない）。部分成功は新しい JSON を push する。

### 3.4 履歴期間

計算に必要な日足を取る。目安は **2年分**（200日移動平均と1年ボラ、52週に余裕を持たせる）。期間不足の指標だけ該当セルを「—」にする。

---

## 4. 計算式

終値系列を \(P_t\)（\(t\) は当該市場の営業日）とする。利回り系列も同じ扱い（水準の差と変化率の意味が違う点は UI の単位で区別する）。

| 項目 | 定義 |
|------|------|
| 最終価格 | 系列の最後の有効終値 \(P_n\) |
| 前日比（%） | \((P_n / P_{n-1} - 1) \times 100\)。利回りは **bp 差**（\((P_n - P_{n-1}) \times 100\)）でもよいが、v1 は他と同じく変化率％で統一する。単位列で「%」または「利回り％」を出す |
| 年初来（%） | 当年最初の営業日終値 \(P_{y0}\) に対し \((P_n / P_{y0} - 1) \times 100\) |
| 52週位置（%） | \( (P_n - L_{52}) / (H_{52} - L_{52}) \times 100 \)。\(H_{52}, L_{52}\) は直近252営業日の高値・安値。分母0なら「—」 |
| 200日乖離（%） | \( (P_n / MA_{200} - 1) \times 100 \)。200営業日未満なら「—」 |
| 1年ボラ | 直近252営業日の日次対数収益の標準偏差 × \(\sqrt{252}\)。パーセント表示（例: 0.18 → 18.0%） |

派生:

| id | 計算 |
|----|------|
| `us_2s10s` | 米10年利回り − 米2年利回り（パーセントポイント） |
| `us_10s30s` | 米30年 − 米10年 |

表示タイムゾーンは **Asia/Tokyo**。`as_of` と各行の `last_date` は ISO 8601 にタイムゾーンオフセットを付けるか、日付のみ＋ヘッダーで JST と明記する。

---

## 5. 色分け

- **騰落（前日比・年初来）**: 正＝緑、負＝赤、0＝ニュートラル。色覚用に符号と数値は残す（色だけに依存しない）。
- **52週位置**: 色分けしない（数値のみ）。必要なら実装時に任意。
- **200日乖離**: 騰落と同じ緑/赤。
- **VIX**: \<20 ニュートラル、20–30 黄、≥30 赤。
- **2s10s**: 値が負（逆転）なら赤。正はニュートラル。
- MOVE / クレジットスプレッドは、Yahoo で値が来た場合のみ「拡大＝赤」などの単純ルールを config の `thresholds` で持てるようにする。v1 で欠測なら色なし。

---

## 6. UI

- 言語: 日本語。
- テーマ: ダーク寄りの表。ビルドツールなし。
- ヘッダー: タイトル、目的文、最終更新（JST）、欠測件数バナー。
- セクション 1〜6 を草案どおりの見出しで並べる。
- 各セクション見出しに優先度バッジ: `必須` / `次に見る` / `上級`。
- 行: 市場または対象、指標名、備考（短文可）、ティッカー、最終値、5指標、最終日付、status。
- 全部展開。折りたたみ禁止。
- 狭い画面は表の横スクロールでよい。
- ETF セクションの日本ティッカーは数値列を「—」または非表示にし、ティッカー文字列を備考側に出す。

優先度マッピング:

**必須**

- 1-1 のうち S&P 500, NASDAQ 100, 日経平均, TOPIX（セクション1-1全体は表示するが、バッジはセクション単位でも行単位でもよい。実装時は **セクション単位** を基本とし、1-1 は必須とする）
- 2-1 米国10年
- 4-1 DXY, USD/JPY
- 5 VIX

**次に見る**

- 1-3 セクター
- 2-2 2s10s とクレジットスプレッド（取れた場合）
- 3 原油・金・銅
- 6 ETFマトリクス全体

**上級**

- 1-2 新興国
- 2-1 TIPS ほか（米10年以外の金利）
- 2-2 FRA-OIS, MOVE
- 3 鉄鉱石・農産物
- 4-3 新興国通貨

セクション単位だと「必須と上級が混在するセクション」がある。**行に `priority: must | next | advanced` を持たせ、見出しはセクション番号、行のバッジで優先度を出す**ことを仕様とする（grilling の「見出しラベル」を満たしつつ混在に耐える）。

---

## 7. `latest.json` の形

```json
{
  "generated_at": "2026-08-27T06:30:00+09:00",
  "source": "yahoo",
  "items": [
    {
      "id": "sp500",
      "status": "ok",
      "last": 5630.12,
      "last_date": "2026-08-26",
      "chg_1d_pct": -0.42,
      "ytd_pct": 12.3,
      "pos_52w_pct": 81.4,
      "dev_200d_pct": 3.1,
      "vol_1y_pct": 16.2
    },
    {
      "id": "move",
      "status": "missing",
      "error": "yahoo_no_data"
    }
  ]
}
```

ラベル・備考・セクションは JSON に重複してもよいが、単一の真実は `config/instruments.yaml` とする。フロントは config を持たないため、**生成時にラベル類を JSON へ埋め込む**（Pages が yaml を読めないため）。

---

## 8. 指標定義（Yahoo シンボル）

`provider` 省略時は `yahoo`。シンボルは v1 の初期値。Yahoo 側の変更で欠測したら config だけ直す。

### 8.1 先進国株価指数（1-1）

| id | 市場 | 指標 | symbol | priority |
|----|------|------|--------|----------|
| sp500 | 米国 | S&P 500 | `^GSPC` | must |
| nasdaq100 | 米国 | NASDAQ 100 | `^NDX` | must |
| russell2000 | 米国 | ラッセル2000 | `^RUT` | next |
| nikkei225 | 日本 | 日経平均株価 | `^N225` | must |
| topix | 日本 | TOPIX | `^TOPX` | must |
| stoxx600 | 欧州 | STOXX Europe 600 | `^STOXX` | next |
| dax | 欧州 | DAX | `^GDAXI` | next |
| cac40 | 欧州 | CAC40 | `^FCHI` | next |
| ftse100 | 欧州（英国） | FTSE 100 | `^FTSE` | next |
| asx200 | その他先進 | S&P/ASX 200 | `^AXJO` | advanced |
| tsx | その他先進 | S&P/TSX | `^GSPTSE` | advanced |
| kospi | その他先進 | KOSPI | `^KS11` | advanced |
| taiex | その他先進 | 台湾加権 | `^TWII` | advanced |

### 8.2 新興国株価指数（1-2）すべて advanced

| id | 市場 | 指標 | symbol |
|----|------|------|--------|
| msci_em | グローバル | MSCI EM | `EEM`（指数そのものが欠ける場合の代用。可能なら `^MSCIEF` 等を試し、ダメなら EEM） |
| nifty50 | インド | Nifty 50 | `^NSEI` |
| sse | 中国・本土 | 上海総合 | `000001.SS` |
| csi300 | 中国・本土 | CSI 300 | `000300.SS` |
| hsi | 中国・香港 | ハンセン | `^HSI` |
| hstech | 中国・香港 | ハンセンテック | `^HSTECH` |
| bovespa | ブラジル | Bovespa | `^BVSP` |
| ipc | メキシコ | IPC | `^MXX` |
| vnindex | ベトナム | VN-Index | `^VNINDEX.VN` または `VNM` へフォールバック |
| jci | インドネシア | JCI | `^JKSE` |

SENSEX は出さない（草案どおり Nifty 主戦）。

### 8.3 米国セクター（1-3）priority: next

| id | セクター | symbol |
|----|----------|--------|
| xlk | 情報技術 | `XLK` |
| xlf | 金融 | `XLF` |
| xle | エネルギー | `XLE` |
| xlv | ヘルスケア | `XLV` |
| xlp | 生活必需品 | `XLP` |
| xlu | 公共事業 | `XLU` |
| xlre | 不動産 | `XLRE` |
| xlb | 資材 | `XLB` |
| xli | 工業 | `XLI` |
| xlc | 通信サービス | `XLC` |
| xly | 一般消費財 | `XLY` |

### 8.4 先進国金利（2-1）

| id | 内容 | symbol | priority | 備考 |
|----|------|--------|----------|------|
| us_2y | 米2年国債利回り | `^IRX` は13週。2年は `^UST2YR` または `2YY=F` を試す。両方欠測なら missing | next | |
| us_10y | 米10年 | `^TNX` | must | Yahoo はパーセント×10 で来る場合あり。**値が 20 超なら /10 して％に正規化** |
| us_30y | 米30年 | `^TYX` | advanced | 同様にスケール補正 |
| us_tips_10y | TIPS 10年 | `^TNX` と TIP では実質金利にならない。Yahoo に安定シンボルがなければ **missing（FRED 後付け: DFII10）** | advanced | |
| jp_10y | 日本10年 | `^TNX-JP` は不安定。`JP10Y=RR` 等を試し、だめなら missing | advanced | |
| de_10y | 独10年 Bund | `^TNX` 系ではなく `DE10Y=RR` 等を試す | advanced | |
| uk_10y | 英10年 Gilts | `GB10Y=RR` 等を試す | advanced | |

金利シンボルは Yahoo で壊れやすい。config に `symbol_fallbacks: []` を置き、上から試す。

### 8.5 イールドカーブ・スプレッド（2-2）

| id | 内容 | provider | priority |
|----|------|----------|----------|
| us_2s10s | 米10年 − 米2年 | derived | next |
| us_10s30s | 米30年 − 米10年 | derived | advanced |
| hy_oas | HY-OAS | fred（v1 missing） | next |
| fra_ois | FRA-OIS | fred（v1 missing） | advanced |

### 8.6 インフレ・商品（3）

| id | カテゴリ | 銘柄 | symbol | priority |
|----|----------|------|--------|----------|
| wti | エネルギー | WTI | `CL=F` | next |
| brent | エネルギー | Brent | `BZ=F` | next |
| ng | エネルギー | 天然ガス | `NG=F` | advanced |
| gold | 貴金属 | 金 | `GC=F` | next |
| silver | 貴金属 | 銀 | `SI=F` | advanced |
| copper | 工業金属 | 銅 | `HG=F` | next |
| iron_ore | 工業金属 | 鉄鉱石 | `TIO=F` 等を試す。だめなら missing | advanced |
| soybean | 農産物 | 大豆 | `ZS=F` | advanced |
| wheat | 農産物 | 小麦 | `ZW=F` | advanced |
| corn | 農産物 | トウモロコシ | `ZC=F` | advanced |

### 8.7 為替（4）

| id | ペア | symbol | priority |
|----|------|--------|----------|
| dxy | DXY | `DX-Y.NYB` | must |
| eurusd | EUR/USD | `EURUSD=X` | next |
| gbpusd | GBP/USD | `GBPUSD=X` | next |
| audusd | AUD/USD | `AUDUSD=X` | next |
| usdcnh | USD/CNH | `CNH=X` | advanced |
| usdcny | USD/CNY | `CNY=X` | advanced |
| usdjpy | USD/JPY | `JPY=X` | must |
| eurjpy | EUR/JPY | `EURJPY=X` | advanced |
| chfjpy | CHF/JPY | `CHFJPY=X` | advanced |
| usdinr | USD/INR | `INR=X` | advanced |
| usdbrl | USD/BRL | `BRL=X` | advanced |
| usdkrw | USD/KRW | `KRW=X` | advanced |
| usdtwd | USD/TWD | `TWD=X` | advanced |

### 8.8 センチメント（5）

| id | 指標 | symbol | priority |
|----|------|--------|----------|
| vix | VIX | `^VIX` | must |
| move | MOVE | Yahoo に安定シンボルなし → missing、FRED 後付け | advanced |
| btc | BTC | `BTC-USD` | next |
| eth | ETH | `ETH-USD` | next |

### 8.9 主要ETF（6）priority: next

米上場は取得する。日本上場は `listed_jp` として文字列のみ（price 取得しない）。

**米国株式**

| 対象 | 取得 symbol | 併記 |
|------|-------------|------|
| S&P 500 | `SPY`（VOO, IVV は併記のみ） | VOO, IVV |
| NASDAQ 100 | `QQQ` | |
| ラッセル2000 | `IWM` | |
| ダウ | `DIA` | |

**日本株式**（数値なし）

| 対象 | 併記 |
|------|------|
| 日経225 | 1321, 1322 |
| TOPIX | 1306, 1308 |
| JPX日経400 | **出さない**（草案の省略推奨に従う） |

**欧州**

| 対象 | symbol |
|------|--------|
| STOXX 600 | `VGK` |
| ユーロ圏 | `EZU` |
| ドイツ | `EWG` |
| フランス | `EWQ` |
| 英国 | `EWU` |

**新興国・個別国**

| 対象 | symbol | 併記 |
|------|--------|------|
| MSCI EM | `EEM` | VWO |
| インド | `INDA` | |
| 中国・本土 | `ASHR` | |
| 中国・香港 | `FXI` | 2801 |
| ブラジル | `EWZ` | |
| ベトナム | `VNM` | |
| 韓国 | `EWY` | |
| 台湾 | `EWT` | |

**グローバル**

| 対象 | symbol | 併記 |
|------|--------|------|
| ACWI | `ACWI` | |
| EAFE | `EFA` | VEA |
| MSCI EM | 上の EEM と重複してよい（同じ id を再利用し二重取得しない） | |

**債券**

| 対象 | symbol |
|------|--------|
| 米国債20年超 | `TLT` |
| 7-10年 | `IEF` |
| 1-3年 | `SHY` |
| HY | `HYG`（JNK 併記） |
| IG 社債 | `LQD` |

同一価格系列を指数と ETF で二重に出してよい（SPY と ^GSPC は別 id）。

---

## 9. FRED 差し込み口（実装しない。形だけ）

`fred.py` の想定インタフェース:

- `fetch(series_id: str, start, end) -> DataFrame`
- 環境変数 `FRED_API_KEY` が無ければ即 missing
- config 例:

```yaml
id: hy_oas
provider: fred
fred_series: BAMLH0A0HYM2
```

v1 で接続コードを本番呼び出ししてはいけない（キーも不要）。

候補シリーズ（後付け用メモ）:

| 指標 | 想定 FRED id |
|------|----------------|
| TIPS 10年実質 | DFII10 |
| HY OAS | BAMLH0A0HYM2 |
| MOVE | MOVEINDEX（利用可否は実装時に確認） |
| 米2年 | DGS2 |
| 米10年 | DGS10 |
| 米30年 | DGS30 |

---

## 10. GitHub Pages / 権限

- 閲覧制限なし。public リポジトリでよい。
- `GITHUB_TOKEN` の `contents: write` で JSON を main に push。
- Pages はリポジトリ Settings → Pages → Branch: `main` / folder: `/docs`。
- カスタムドメインなし。

---

## 11. 実装時の作業順（このリポジトリではまだやらない）

1. `config/instruments.yaml` を本セクション8から起こす。
2. 取得・計算スクリプト。ローカルで1回 Yahoo を叩いて欠測シンボルを調整。
3. `docs/index.html`。
4. `.github/workflows/update.yml`。
5. Pages 設定と README。

---

## 12. 受け入れ条件（実装フェーズ用）

- ブラウザで `docs/index.html` を開き、JSON があれば表が出る。
- 必須行（S&P500, NASDAQ100, 日経, TOPIX, 米10年, DXY, USD/JPY, VIX）が、Yahoo が生きていれば `ok`。
- missing 行が表から消えない。
- 認証画面がない。
- Actions の YAML に平日 cron と `workflow_dispatch` がある。
