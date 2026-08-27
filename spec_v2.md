# 仕様 v2: 欠測 10 件を取得する計画

> 前提：v1（`spec.md`）は Yahoo 主戦、FRED はスタブ、日本上場 ETF はティッカー併記のみ。  
> 公開 UI は欠測でも **行を消さず「データなし」** と出す。本計画はその表示契約を維持したまま、現状 10 件を埋める。  
> 実装はこの文書に従う。v1 の非目標のうち、本計画で覆すものだけを明示する。

---

## 0. 現状（観測）

`docs/data/latest.json` の `missing_count: 10`。バナー文は

`欠測 10 件（行は残し「データなし」表示）`

実体は次の 10 行。失敗理由は JSON の `error`。

| # | id | 表示名 | provider | ticker / series | error | 優先度 |
|---|-----|--------|----------|-----------------|-------|--------|
| 1 | `hstech` | ハンセンテック | yahoo | `^HSTECH` | `yahoo_no_data` | advanced |
| 2 | `us_tips_10y` | TIPS 10年実質金利 | fred | DFII10 | `fred_not_implemented` | advanced |
| 3 | `jp_10y` | 日本10年国債利回り | yahoo | `JP10Y=RR` | `yahoo_no_data` | advanced |
| 4 | `de_10y` | 独10年 Bund | yahoo | `DE10Y=RR` | `yahoo_no_data` | advanced |
| 5 | `uk_10y` | 英10年 Gilts | yahoo | `GB10Y=RR` | `yahoo_no_data` | advanced |
| 6 | `hy_oas` | HY-OAS | fred | BAMLH0A0HYM2 | `fred_not_implemented` | next |
| 7 | `fra_ois` | FRA-OIS | fred | シリーズ未設定 | `fred_not_implemented` | advanced |
| 8 | `move` | MOVE | fred | MOVEINDEX | `fred_not_implemented` | advanced |
| 9 | `etf_nk225` | 日経225（日本上場 ETF） | listed_jp | 1321, 1322 | `listed_jp_no_price` | next |
| 10 | `etf_topix` | TOPIX（日本上場 ETF） | listed_jp | 1306, 1308 | `listed_jp_no_price` | next |

分類:

| 群 | 件数 | 原因 |
|----|------|------|
| A. Yahoo シンボル不良 | 4 | `hstech`, `jp_10y`, `de_10y`, `uk_10y` |
| B. FRED 未実装 | 4 | `us_tips_10y`, `hy_oas`, `fra_ois`, `move` |
| C. v1 で意図的に取らない | 2 | `etf_nk225`, `etf_topix` |

---

## 1. ゴールと非目標（v2）

### 1.1 ゴール

- 上記 10 行を、可能な限り `status: ok` にする。
- 取れない行は **これまでどおり行を残し「データなし」**。表から削除しない。
- 取得経路は既存の `yahoo` / `fred` / `listed_jp` に収める。新プロバイダは増やさない。
- 5 指標（前日比・年初来・52週位置・200日乖離・1年ボラ）は既存 `compute.py` を流用する。
- 失敗方針は v1 と同じ: 銘柄単位で継続、**全件 missing のときだけ** job 失敗。

### 1.2 非目標

- 閲覧制限、分足、シグナル自動判定は引き続きやらない。
- FRA-OIS の厳密な ICE 先物−OIS 系列を有料ソースから取ることはしない（無料プロキシで代替、取れなければ missing）。
- 日次履歴 JSON の git 保管はしない。
- 日本上場 ETF をセクション6の全行に広げることはしない（欠測している 2 行だけ価格を取る）。

### 1.3 v1 からの変更点

| v1 | v2 |
|----|-----|
| FRED はスタブのみ。本番呼び出し禁止 | `FRED_API_KEY` があるときだけ本番呼び出し |
| 日本上場 ETF は価格取得しない | `etf_nk225` / `etf_topix` は Yahoo の `.T` ティッカーで終値を取る |
| 金利は Yahoo の `*10Y=RR` のみ | Yahoo 失敗時は FRED 長期金利シリーズへフォールバック |

---

## 2. 行を残し「データなし」契約（不変）

実装しても失敗しうる。次は v1 と同じで固定する。

- JSON: `status: "missing"` + `error` 文字列。行オブジェクト自体は出す。
- UI: 数値セルは「データなし」。スパークラインは空。ステータス列は `missing`。
- ヘッダー: `欠測 N 件（行は残し「データなし」表示）`。N は `missing_count`。
- `listed_jp` だった行も、価格が取れなければ同じ表示（ティッカー文字列は残す）。

---

## 3. 指標ごとの取得計画

試行順は上から。全部失敗したら missing。成功したシンボルは JSON の `resolved_symbol`（または既存どおり `ticker` 上書き）に残す。

### 3.1 `hstech`（Yahoo）

Hang Seng TECH 指数 `^HSTECH` は yfinance で空になることがある。

| 順 | symbol | 意味 |
|----|--------|------|
| 1 | `^HSTECH` | 指数（現状） |
| 2 | `HSTECH.HI` | 香港指数ボード表記 |
| 3 | `3032.HK` | Hang Seng TECH Index ETF（価格水準は指数と異なる。note に「ETF 代用」） |

config: `symbol_fallbacks: ["HSTECH.HI", "3032.HK"]`  
代用 ETF を使ったときは `note` を「指数欠測時は 3032.HK で代用」にする（既存 TOPIX / MSCI EM と同じ型）。

### 3.2 先進国 10 年利回り（Yahoo → FRED）

`*10Y=RR` は Yahoo 側が死んでいる。指数先物や ETF では利回り％にならないので使わない。

| id | Yahoo 一次 | Yahoo 二次 | FRED フォールバック | 単位 |
|----|------------|------------|---------------------|------|
| `jp_10y` | `JP10Y=RR` | （なし。壊れやすい別名は増やさない） | `IRLTLT01JPM156N`（OECD 日本 10 年） | 利回り％ |
| `de_10y` | `DE10Y=RR` | | `IRLTLT01DEM156N` | 利回り％ |
| `uk_10y` | `GB10Y=RR` | | `IRLTLT01GBM156N` | 利回り％ |

実装: 各 instrument に `provider: yahoo` を維持し、`fred_series` を併記する。`update.py` は Yahoo が空なら `fred.fetch(fred_series)` を試す。FRED キー無し・シリーズ欠測なら missing。

OECD 長期金利は月次のことがある。その場合:

- 日次 5 指標のうち計算不能なセルは「—」（既存の期間不足ルール）。
- `last` と `last_date` は最終観測を出す。月次でも `ok` にしてよい。
- `note` に「FRED OECD 長期金利（観測頻度はソース依存）」を書く。

### 3.3 `us_tips_10y`（FRED）

- `provider: fred`
- `fred_series: DFII10`（Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity, Inflation-Indexed）
- Yahoo 代用はしない（`^TNX` や TIP は実質金利ではない。v1 と同じ）。

### 3.4 `hy_oas`（FRED）

- `provider: fred`
- `fred_series: BAMLH0A0HYM2`（ICE BofA US High Yield OAS）
- 単位 bp。既存 `thresholds.wider_is_red` を維持。
- 代用に HYG スプレッドは使わない（水準の意味が違う）。

### 3.5 `move`（FRED）

- `provider: fred`
- `fred_series: MOVEINDEX`
- 実装時に FRED でシリーズが 404 / 権限なしなら、Yahoo `^MOVE` を一度だけ試し、だめなら missing のまま。
- 有料 Bloomberg は使わない。

### 3.6 `fra_ois`（プロキシ、取れなければ missing）

厳密な 3m FRA−OIS は FRED に安定シリーズがない。v2 の方針:

1. config に `fred_series` を **入れない**（空のまま呼び出すと誤った ID を叩く）。
2. 無料で近いものとして **試さない** のが既定（TEDRATE は銀行間−T-bill であり FRA-OIS ではない）。
3. 行は残す。`note` を「無料ソースに安定シリーズなし。取得できず「データなし」」に更新する。
4. 後で安定 ID が見つかったら config だけ足す（差し込み口は FRED 実装で既に用意する）。

つまり **10 件中、計画時点で埋めないと決めるのは `fra_ois` のみ**。受け入れ条件の「欠測を減らす」対象から外し、バナー件数は最大 1 を許容する。

代替をユーザーが明示した場合のみ、そのシリーズを `fred_series` に入れる。

### 3.7 日本上場 ETF 2 行（Yahoo）

v1 の `listed_jp` は価格を取らない。v2 ではこの 2 行だけ Yahoo 化する。

| id | 一次 symbol | fallback | 併記（価格は取らない） |
|----|-------------|----------|------------------------|
| `etf_nk225` | `1321.T` | `1322.T` | 1322 |
| `etf_topix` | `1306.T` | `1308.T` | 1308 |

- `provider: yahoo` に変更（`listed_jp` は使わない）。
- `listed_also` または既存 `listed_jp` フィールドで他コードをティッカー列に残す。
- `note`: 「日本上場。価格は Yahoo `.T`。欠測時はデータなし」。
- セクション1の指数（`^N225`, `^TOPX` / `1306.T`）と価格系列が近くても、id は別のまま（v1 と同じ「指数と ETF は二重に出してよい」）。

---

## 4. FRED プロバイダ実装

v1 のスタブを本番呼び出しに差し替える。呼び出しはキーがあるときだけ。

### 4.1 インタフェース

`src/providers/fred.py`

```
fetch(series_id: str) -> pandas.Series | None
```

- 環境変数 `FRED_API_KEY` が無ければ `None`（例外でジョブ全体を落とさない）。
- HTTP: `https://api.stlouisfed.org/fred/series/observations`
  - `series_id`, `api_key`, `file_type=json`, `observation_start` = 約 2 年前（Yahoo と同じ窓）。
- 観測値 `"."` は欠測として落とす。
- 日付インデックス、float の終値相当 Series を返す。空なら `None`。
- タイムアウト・HTTP エラーはログして `None`。リトライは 1 回まで。

依存: `urllib` 標準ライブラリで足りる。新規 PyPI パッケージは増やさない。

### 4.2 `update.py`

```
provider == "fred":
  series = fred.fetch(inst["fred_series"])
  なければ missing(..., "fred_no_data" | "fred_no_key")

provider == "yahoo":
  既存 fetch_yahoo
  空 かつ inst に fred_series がある:
    FRED フォールバック
```

`listed_jp` 分岐は、config から当該 2 行が消えたあと死コードになる。他に `listed_jp` が残らなければ分岐を削除してよい。残るなら従来どおり missing。

### 4.3 GitHub Actions / ローカル

- Actions: repository secret `FRED_API_KEY` を `env` に渡す。未設定でもジョブは成功（FRED 行だけ missing）。
- ローカル: 同じ環境変数。キーなしで Yahoo 分は更新できる。
- キーを JSON・ログ・HTML に出さない。

FRED 利用規約: 公開ダッシュボードに観測値を載せる用途。過度なポーリングはしない（平日 1 日 1 回の既存 cron に乗せる。シリーズは 4 本 + 金利フォールバック最大 3 本）。

---

## 5. config 変更一覧

`config/instruments.yaml` のみ。id / section / 優先度 / 単位 / 閾値は変えない。

| id | 変更 |
|----|------|
| `hstech` | `symbol_fallbacks: ["HSTECH.HI", "3032.HK"]`。note 追記 |
| `jp_10y` | `fred_series: IRLTLT01JPM156N` |
| `de_10y` | `fred_series: IRLTLT01DEM156N` |
| `uk_10y` | `fred_series: IRLTLT01GBM156N` |
| `us_tips_10y` | 変更なし（実装側が `fred` を呼ぶ） |
| `hy_oas` | 変更なし |
| `fra_ois` | note を「無料安定シリーズなし」に。`fred_series` は置かない |
| `move` | 変更なし。任意で `symbol: "^MOVE"` と yahoo フォールバックを足してよい |
| `etf_nk225` | `provider: yahoo`, `symbol: "1321.T"`, `symbol_fallbacks: ["1322.T"]`, `listed_also: ["1322"]` |
| `etf_topix` | `provider: yahoo`, `symbol: "1306.T"`, `symbol_fallbacks: ["1308.T"]`, `listed_also: ["1308"]` |

---

## 6. UI

`docs/index.html` の「データなし」ロジックは変更しない。

任意の小さな追記（必須ではない）:

- missing 行の `error` はデバッグ用なので画面に出さない（現状どおり）。
- FRED フォールバックで `ok` になった行は、ティッカー列に FRED id が出てよい。

受け入れは「10 行が表に残り、取れた行は数値が入り、取れない行（想定は `fra_ois`）だけデータなし」。

---

## 7. 作業順

1. **config** — 上表どおり yaml を直す。
2. **FRED 実装** — `fred.py` + `update.py` の呼び出しと Yahoo→FRED フォールバック。キー無しパスの単体確認。
3. **Yahoo フォールバック** — `hstech` と日本 ETF。ローカルで `yfinance` を一度叩いて空でないシンボルを確定。空なら yaml を直す。
4. **Actions** — `FRED_API_KEY` を secret 経由で渡す。未設定でも落ちないことを確認。
5. **受け入れ** — `latest.json` の `missing_count` が 1 以下（残るなら `fra_ois`）。HTML バナーと表の行数が変わっていないこと。

実装は本 spec を書いたあと。本文書は計画であり、このコミットで取得コードを動かさなくてよい。

---

## 8. 受け入れ条件

- 欠測バナーの文言は維持。件数だけ実数に追従する。
- 次はキーと Yahoo が生きていれば `ok` になる:  
  `hstech`, `us_tips_10y`, `jp_10y`, `de_10y`, `uk_10y`, `hy_oas`, `move`, `etf_nk225`, `etf_topix`
- `fra_ois` は missing のままでよい。行は残る。
- `FRED_API_KEY` 無しでもジョブは成功し、FRED 依存行だけ missing。
- 必須行（S&P500 等）の取得は壊さない。
- 全件 missing のときだけ job 失敗、は維持。

---

## 9. Key Decisions

| 決定 | 理由 |
|------|------|
| 新プロバイダを増やさない | 運用と Actions を単純に保つ |
| 金利 3 本は Yahoo 優先、FRED OECD が保険 | 日次が取れれば日次。取れなければ月次でも水準は出る |
| TIPS / HY-OAS / MOVE は FRED 本番 | Yahoo に正しい系列がない |
| FRA-OIS は欠測のまま行を残す | 無料で意味が同じ系列がない。誤った TED 代用はしない |
| 日本 ETF 2 行だけ Yahoo `.T` | 欠測解消に必要最小。他の日本併記は触らない |
| HSTECH は ETF 代用を最後に許す | 指数と水準は違うが、方向と 5 指標は使える。note で明示 |
| FRED キー無しは missing で継続 | ローカルと secret 未設定を落とさない |

---

## 10. リスクと切り戻し

| リスク | 対応 |
|--------|------|
| FRED レート制限 / キー無効 | 行 missing。前回 JSON は部分成功なら上書きされる |
| OECD 金利が月次 | 5 指標の一部が「—」。水準は出す |
| `MOVEINDEX` が FRED 非公開 | Yahoo `^MOVE`、だめなら missing |
| `3032.HK` が指数と乖離 | note 表示。指数が復活したら fallback 順で指数が勝つ |
| `.T` が yfinance で空 | fallback 銘柄。両方空ならデータなし |

切り戻し: yaml の provider / fallback を戻し、`fred.py` をキー無しで `None` にする。UI 契約は変えていないので HTML 切り戻しは不要。

---

## 11. PR Plan

### PR1: config と FRED スタブ解除

- 対象: `config/instruments.yaml`, `src/providers/fred.py`, `src/update.py`, `.github/workflows/update.yml`（secret 配線）
- 依存: なし
- 内容: セクション 4–5。キー無しでテスト可能。

### PR2: Yahoo フォールバック確定

- 対象: `config/instruments.yaml`（実測で空だったシンボルの差し替え）, 必要なら `src/providers/yahoo.py`
- 依存: PR1
- 内容: `hstech` と日本 ETF、金利 Yahoo 側の実測。

### PR3: ドキュメント

- 対象: `README.md`（FRED キー、欠測の残件）
- 依存: PR1
- 内容: secret の置き方と、残る `fra_ois` の説明。

各 PR は独立にマージ可能。PR2 はローカルで Yahoo を叩いた結果で yaml だけ直す最小差分が望ましい。
