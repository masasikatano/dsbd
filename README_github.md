# GitHub Pages での公開手順

このリポジトリは `docs/` フォルダを静的サイトとして GitHub Pages で公開します。

## 1. リポジトリ設定

1. GitHub リポジトリページを開く
2. **Settings** → 左メニュー **Pages** を選択
3. **Build and deployment** セクションで以下を設定
   - **Source**: `Deploy from a branch`
   - **Branch**: `main`
   - **Folder**: `/docs`
4. **Save** をクリック

設定後、数分で `https://<username>.github.io/<repository-name>/` でアクセスできるようになります。

## 2. 公開対象ファイル

GitHub Pages には `docs/` 以下のファイルが公開されます。

```
docs/
├── index.html        # ダッシュボード UI（メインページ）
├── detail.html       # 指標詳細ページ
├── common.js         # UI 共通スクリプト
├── data/
│   └── latest.json   # 生成済みスナップショット
└── favicon.ico
```

`docs/data/latest.json` は GitHub Actions またはローカル実行で更新します。`docs/` 外の `src/` や `config/` などは公開されません。

## 3. データ更新の自動化

`.github/workflows/update.yml` が以下のタイミングで実行されます。

- 平日 21:30 UTC（日本時間 火〜土 6:30）
- 手動実行：`Actions` タブ → `Update dashboard data` → `Run workflow`

このワークフローは Yahoo Finance などから終値を取得し、`docs/data/latest.json` を `[skip ci]` 付きで `main` ブランチに push します。push 後、GitHub Pages が自動で再デプロイされます。

### 必要な権限

`GITHUB_TOKEN` に `contents: write` が必要です。デフォルトで有効になっていますが、変更している場合は Settings → Actions → General → **Workflow permissions** で確認してください。

## 4. API キー設定（オプション）

API キーを設定すると、一部の指標がより安定して取得できます。未設定でもジョブは成功し、取得できない行だけ「データなし」と表示されます。

| キー | 用途 |
|------|------|
| `FRED_API_KEY` | TIPS 10年・HY-OAS・MOVE・先進国10年のフォールバック |
| `EODHD_API_KEY` | CSI 300・VN-Index・USD/CNH の日次履歴取得 |

### 設定手順

1. リポジトリの **Settings** → **Secrets and variables** → **Actions** を開く
2. **New repository secret** をクリック
3. 名前に `FRED_API_KEY` または `EODHD_API_KEY`、値に取得した API キーを入力
4. **Add secret** をクリック

ローカルでは `.env` に同名で記述します。`.env` は git 管理対象外です。取得したキーはログや JSON に出力しないでください。

## 5. ローカルで更新して手動公開

自動更新を待たずに手動で最新データを反映する場合：

```bash
./run_local.sh --no-serve
```

これで `docs/data/latest.json` が更新されます。変更を commit・push すると、GitHub Pages に反映されます。

```bash
git add docs/data/latest.json
git commit -m "Update dashboard data"
git push origin main
```

## 6. 注意事項

- カスタムドメインは使用しません
- 閲覧制限はありません（公開リポジトリの場合）
- `docs/data/latest.json` は Git 管理対象ですが、API キーは絶対に含めないでください
- 更新後にページが変わらない場合は、ブラウザのキャッシュ削除または数分待ってから再読み込みしてください
