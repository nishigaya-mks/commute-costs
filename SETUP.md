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

## トラブルシューティング

### 「gspread.exceptions.SpreadsheetNotFound」エラー
→ サービスアカウントにスプレッドシートが共有されていません。手順2-3を確認。

### 「google.auth.exceptions.DefaultCredentialsError」エラー
→ Secretsの設定が間違っています。JSONの内容を正確にコピーしてください。

### データが保存されない
→ サービスアカウントの権限が「閲覧者」になっていないか確認。「編集者」が必要です。
