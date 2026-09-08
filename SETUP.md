# Streamlit Cloud デプロイ手順

## 1. Google Cloud Console でサービスアカウント作成

1. [Google Cloud Console](https://console.cloud.google.com/) にアクセス
2. 新しいプロジェクトを作成（または既存を使用）
3. 「APIとサービス」→「ライブラリ」から以下を有効化:
   - Google Sheets API
   - Google Drive API
4. 「APIとサービス」→「認証情報」→「認証情報を作成」→「サービスアカウント」
5. サービスアカウント作成後、「キー」タブ→「鍵を追加」→「新しい鍵を作成」→ JSON形式
6. ダウンロードしたJSONファイルを保管（後で使用）

## 2. Google スプレッドシート作成

1. [Google Sheets](https://sheets.google.com/) で新しいスプレッドシートを作成
2. スプレッドシートを開き、URLをコピー
3. 「共有」→ サービスアカウントのメールアドレス（`xxx@xxx.iam.gserviceaccount.com`）を追加
4. 権限は「編集者」に設定

## 3. GitHub リポジトリ作成

1. GitHubで新しいリポジトリを作成
2. `app_cloud` フォルダの内容をアップロード:
   ```
   app_cloud/
   ├── main.py
   ├── pages/
   ├── utils/
   └── requirements.txt
   ```

## 4. Streamlit Cloud でデプロイ

1. [share.streamlit.io](https://share.streamlit.io/) にGitHubでログイン
2. 「New app」をクリック
3. リポジトリ、ブランチ、メインファイル（`main.py`）を選択
4. 「Advanced settings」→「Secrets」に以下を貼り付け:

```toml
[gcp_service_account]
type = "service_account"
project_id = "your-project-id"
private_key_id = "（JSONの private_key_id）"
private_key = "（JSONの private_key）"
client_email = "（JSONの client_email）"
client_id = "（JSONの client_id）"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "（JSONの client_x509_cert_url）"

[spreadsheet]
url = "https://docs.google.com/spreadsheets/d/YOUR_SPREADSHEET_ID/edit"
```

5. 「Deploy!」をクリック

## 5. 完了

デプロイ後、発行されたURLにスマホからアクセスできます。
ブックマークしておくと便利です。

---

## スリープ対策（推奨）

Streamlit Community Cloud の無料枠は、一定時間（目安 12 時間）アクセスがないとアプリをスリープさせる。
スリープ後の初回アクセスは復帰ボタンを押してから起動完了まで 1〜2 分かかる。

このリポジトリには、6 時間ごとにヘッドレスブラウザでアプリを開いてスリープを防ぐ
GitHub Actions（`.github/workflows/keep-alive.yml`）が入っている。有効化するには:

1. GitHub のリポジトリ → Settings → Secrets and variables → Actions → **Variables** タブ
2. 「New repository variable」で以下を登録:
   - Name: `STREAMLIT_APP_URL`
   - Value: デプロイ済みアプリの URL（例: `https://xxxx.streamlit.app`）
3. Actions タブ → 「Keep Streamlit app awake」→ 「Run workflow」で一度手動実行し、成功することを確認

補足:
- 単純な HTTP GET（curl 等）では静的 HTML が返るだけで Python 側は起動しないため、Playwright で実際にページを開いている。
- GitHub Actions のスケジュール実行は、リポジトリに 60 日間コミットがないと自動で無効化される。無効化された場合は Actions タブから再有効化する。
- スリープ画面が出た場合の起動時間そのものは短くできない。起動時間が気になる場合は、常時稼働の有料ホスティング（Streamlit Community Cloud 有料枠、Cloud Run 等）への移行を検討する。

---

## レシート読み取り機能（任意）

給油レシート画像を Claude API で読み取り、給油記録フォームに自動入力する機能。

1. Anthropic の API キーを用意する（https://console.anthropic.com/）
2. Streamlit Cloud の Settings → Secrets（ローカルは `.streamlit/secrets.toml`）に以下を追記:

   ```toml
   [anthropic]
   api_key = "sk-ant-..."
   ```

未設定の場合、給油記録ページに読み取り UI は表示されない（他機能への影響なし）。

---

## トラブルシューティング

### 「gspread.exceptions.SpreadsheetNotFound」エラー
→ サービスアカウントにスプレッドシートが共有されていません。手順2-3を確認。

### 「google.auth.exceptions.DefaultCredentialsError」エラー
→ Secretsの設定が間違っています。JSONの内容を正確にコピーしてください。

### データが保存されない
→ サービスアカウントの権限が「閲覧者」になっていないか確認。「編集者」が必要です。
