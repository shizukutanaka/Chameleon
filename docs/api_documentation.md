# Chameleon Audio Processor - API ドキュメント

このドキュメントは `api_server.py` が提供する REST API を安全に利用するための実践的なガイドです。CLI ワークフローと同様に、すべての通信は HTTPS を前提とし、`SecurityValidator` によるパス・URL 検証方針を遵守します。HTTP はサポートされません。

## 1. 接続要件 / Base URL

- **Base URL**: `CHAMELEON_BASE_URL` 環境変数で指定した HTTPS エンドポイントを使用します。各組織のリバースプロキシまたは API ゲートウェイで公開してください。ローカル開発時は `http://localhost:8080`、本番環境では必ず HTTPS を使用してください。
- **リクエスト ID**: すべての呼び出しで `X-Request-ID` ヘッダーを送信すると追跡が容易になります。未指定の場合はサーバーが自動生成し、応答ヘッダーに反映します。
- すべてのクライアントは TLS 証明書を検証し、HTTP を使用しないでください。
- CORS は `CHAMELEON_ALLOWED_ORIGINS` で列挙した HTTPS ドメインのみ許可されます。

## 2. 認証 / Authentication

API はセッションベースの認証を行います。ログイン成功後に返却されるトークンは後続リクエストの `Authorization: Bearer <token>` ヘッダーで使用します。

### 2.1 ログイン

```http
POST /auth/login
Content-Type: application/json

{
  "username": "operator",
  "password": "********",
  "clearance_level": "SECRET"
}
```

- **レスポンス**: 成功時は `token` と `expires_at` を返します。
- 失敗時は `success: false` と `error` メッセージを返します。

### 2.2 ログアウト

```http
POST /auth/logout
Authorization: Bearer <token>
```

- サーバー側でセッションが無効化されます。

## 3. エンドポイント / Endpoints

### 3.1 ファイルアップロード

```
POST /audio/upload
Content-Type: multipart/form-data
Authorization: Bearer <token>
```

- **フォームフィールド**: `file` (必須)。許可拡張子は `.wav`、`.wave`、`.flac`。サイズ上限は 100MB です。
- サーバーは安全なアップロードディレクトリ（`CHAMELEON_UPLOAD_DIR` で構成。未指定時は OS の一時領域配下の `chameleon/uploads/`）に保存し、`stored_name` を応答します。

### 3.2 オーディオ解析

```http
POST /audio/analyze
Content-Type: application/json
Authorization: Bearer <token>

{
  "file_name": "stored_name.wav"
}
```

- `file_name` には `/audio/upload` の応答で受け取った `stored_name` を指定します。URL を指定した場合は `SecurityValidator.validate_url()` により拒否されます。
- 成功応答はメタデータ (`duration`, `sample_rate`, `peak_level` など) を含む `AudioAnalysisResponse` です。

### 3.3 オーディオ正規化

```http
POST /audio/normalize
Content-Type: application/json
Authorization: Bearer <token>

{
  "file_name": "uploaded_file.wav",
  "target_peak": 0.95,
  "output_format": "wav"
}
```

- 正規化はアップロード済みファイルを対象とします。成功時は `output_file` に一時ディレクトリ内のファイル名を返します。

### 3.4 ファイルダウンロード

```http
GET /audio/download/{file_name}
Authorization: Bearer <token>
```

- 正規化結果を取得する際に利用します。`file_name` は `/audio/normalize` 応答で返された名前を使用してください。

### 3.5 バッチジョブ

#### 提出

```http
POST /batch/submit
Authorization: Bearer <token>
Content-Type: application/json

{
  "files": ["uploaded_file.wav", "uploaded_file_2.wav"],
  "operation": "normalize",
  "options": {}
}
```

- 事前に `/audio/upload` でファイルを登録しておく必要があります。
- `operation` は `analyze` または `normalize` のみに対応します。
- 応答は `job_id` と推定処理時間 (`estimated_duration`) を返します。

#### ステータス取得

```http
GET /batch/status/{job_id}
Authorization: Bearer <token>
```

- 応答には `status` (`pending`, `processing`, `completed`, `failed`) と進捗情報が含まれます。
- ジョブ所有者、または `SECRET` 以上のクリアランスを持つユーザーのみが参照できます。
- 完了済みジョブは最大 `SECURITY_CONFIG['max_job_history']` 件まで履歴として保持され、超過分は自動的にアーカイブされます。

### 3.6 システムステータス

```http
GET /system/status
Authorization: Bearer <token>
```

- 稼働状況、稼働時間、ジョブ統計などを取得します。
- `memory_usage` や `cpu_usage` は `psutil` が導入されている場合に実測値を返します。
- `active_sessions` は現在有効なセッション数、`last_request_timestamp` は直近の認証済みリクエスト時刻 (UTC) を示します。

### 3.7 監査ログ参照

```http
GET /audit/log?limit=100
Authorization: Bearer <token>
```

- `audit` 権限が必要です。直近の監査イベントを JSON 形式で返します。

### 3.8 ヘルスチェック / Health Check

```http
GET /health
```

- 認証不要の軽量エンドポイントです。稼働確認やロードバランサーのヘルスチェックで利用してください。
- 応答には `status`, `uptime_seconds`, `timestamp` が含まれ、サービスの稼働状況を即座に把握できます。

## 4. セキュリティ留意事項 / Security Notes

- **絶対パス**: API に送信するファイルパスは絶対パスである必要があります。`SecurityValidator.validate_file_path()` が確認します。
- **URL 検証**: 外部 URL はサポートされません。アップロード前に独自に検証し、HTTPS のみを利用してください。
- **監査ログ**: すべての操作は `~/.chameleon/logs/api-audit.log` に記録されます。ローテーションは `SecurityValidator` により管理され、世界書き込み不可の権限が要求されます。
- **レート制限**: `SECURITY_CONFIG['enable_rate_limiting']` が `True` の場合、組織ポリシーに従って API ゲートウェイ側で制御してください。
- **セッション管理**: `SECURITY_CONFIG['session_timeout']` および `SECURITY_CONFIG['max_session_idle_seconds']` により期限切れとアイドルタイムアウトを強制します。
- **ファイル所有権**: `/audio/*` および `/batch/*` 系エンドポイントは、アップロード時に記録された所有者とリクエスト送信者を突き合わせてアクセスを制御します。`SECRET` 以上のクリアランスを持つ利用者のみが他者のファイルへアクセスできます。
- **監査追跡**: 各操作は `X-Request-ID` を含む監査ログとして永続化されます。相関分析のため同一 ID を用いてクライアント側ログを保持してください。

## 5. エラー応答 / Error Handling

共通の HTTP ステータスコードとエラーメッセージは以下の通りです。

| ステータス | 説明 |
|---------|------|
| 400 | 入力値またはファイル検証に失敗 (`SecurityValidator` による拒否など) |
| 401 | 認証失敗またはセッション期限切れ |
| 403 | 権限不足 |
| 404 | ファイルまたはジョブが存在しない |
| 413 | ファイルサイズ上限超過 |
| 429 | レート制限違反 (ゲートウェイ設定に依存) |
| 500 | サーバー内部エラー |

例:

```json
{
  "detail": "File not found"
}
```

## 6. 運用ベストプラクティス / Operational Guidance

- **事前検証**: アップロード前にローカルでファイルサイズと拡張子をチェックしてください。
- **監査対策**: `Authorization` トークンの発行・失効を必ず監査ログに記録し、インシデント時には `api-audit.log` を保全してください。
- **一時ファイルの処理**: バッチ処理完了後は `/audio/download` で必要ファイルを取得し、`download` 応答後は不要な一時データを削除する運用を検討してください。
- **環境変数**: `CHAMELEON_ALLOWED_ORIGINS`、`CHAMELEON_ALLOWED_HOSTS`、`CHAMELEON_UPLOAD_CHUNK_SIZE`、`CHAMELEON_SECURITY_LOG_DIR` 等をデプロイ時に必ず見直してください。

---

このドキュメントは `security_validator.py` のポリシーと `api_server.py` の実装に基づいています。API の拡張や設定変更を行う場合は、同ファイルを確認し、必要に応じてテスト (`python -m unittest test_framework.SecurityTests`) を追加してください。
