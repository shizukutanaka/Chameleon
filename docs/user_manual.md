# Chameleon Audio Processor - ユーザーマニュアル / User Manual

## 1. 概要 / Overview

- **日本語**: Chameleonは政府・企業向けの決定論的オーディオ処理ツールです。コマンドライン中心のワークフローと強制的な入力検証により、安全かつ再現性の高い運用を提供します。
- **English**: Chameleon is a deterministic audio processing toolkit for regulated environments. It focuses on CLI-driven workflows, strict validation, and auditable execution.

### 主な機能 / Key Capabilities

- **セキュアCLI**: `chameleon_cli.py` と `enterprise_cli.py` が絶対パス・監査ログ・多言語メッセージを提供
- **バッチ自動化**: `batch_automation.py` が検証済みYAML/JSON設定によるワークフロー実行をサポート
- **統合バリデーション**: `security_validator.py` がパス・拡張子・サイズ・URL・ディレクトリ権限を検証
- **監査ログ**: 主要操作が `~/.chameleon/logs/` にローテーション出力され、改ざん防止の権限設定を適用
- **テストスイート**: `test_framework.SecurityTests` と `test_framework.py` がセキュリティ・機能回帰を検証

## 2. システム要件 / Requirements

- **OS**: Windows 10/11, macOS 12+, Linux (Ubuntu 20.04+)
- **CPU**: 4コア以上 (推奨 8コア)
- **メモリ**: 8GB以上 (推奨16GB)
- **ストレージ**: 2GB以上の空き容量
- **Python**: 3.9 以上
- **ネットワーク**: HTTPS対応の内部リポジトリまたは検証済みアセットにアクセス可能な環境

## 3. インストール手順 / Installation

```bash
git clone <trusted_repository_url>
cd Chameleon
python -m venv .venv
. .venv/bin/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
```

### 初期テスト / Baseline Tests

```bash
python -m unittest test_framework.SecurityTests
python test_framework.py
```

テスト後、`~/.chameleon/logs/` に監査ログが作成されることを確認してください。

## 4. クイックスタート / Quick Start

- **単体処理 / Single File**
  ```bash
  python chameleon_cli.py analyze /absolute/path/input.wav --json --dry-run
  python chameleon_cli.py process --normalize /absolute/path/input.wav --output-dir=/absolute/path/output
  ```

- **Enterprise CLI**
  ```bash
  python enterprise_cli.py batch-process --directory /absolute/path/input --operation normalize
  ```

- **バッチ自動化 / Batch Automation**
  ```python
  from batch_automation import BatchAutomation

  automation = BatchAutomation()
  workflow = automation.create_workflow("/absolute/path/workflow.yaml")
  automation.execute(workflow.id)
  ```

## 5. セキュリティ運用 / Security Operations

- **絶対パス必須**: すべてのCLI引数と設定ファイル項目は絶対パスで指定すること。
- **URL検証**: 外部URLは `security_validator.validate_url()` による検証が必要。HTTPスキームや未登録ホストは拒否されます。
- **監査ログ**: `~/.chameleon/logs/` に出力される `chameleon_security.log`、`enterprise_cli.log`、`api-audit.log` を定期レビューしてください。
- **権限管理**: `.chameleon/logs/` が世界書き込み不可 (POSIX 0750) であること、`CHAMELEON_ALLOWED_ORIGINS` が信頼済みHTTPSドメインのみを含むことを確認してください。
- **定期テスト**: 運用設定変更時は `python -m unittest test_framework.SecurityTests` を再実行し、結果を記録します。

## 6. 詳細機能 / Detailed Features

- **音声解析**: `analyze_audio_fast()` がピーク測定やメタデータ抽出を実行
- **音声正規化**: `normalize_audio_fast()` が目標ピーク (`AudioNormalizationRequest.target_peak`) を強制
- **ワークフロー実行**: `BatchAutomation` が検証済み設定ファイルを読み込んで依存関係を解決
- **API連携**: `api_server.py` を起動し、リバースプロキシ越しに HTTPS で `/audio/analyze` や `/batch/submit` を利用
- **監査**: `log_audit_event()` が操作履歴をJSON形式で記録し、SecureFileOperationsが改ざんを防止

## 7. 設定とカスタマイズ / Configuration

- **環境変数**
  - `CHAMELEON_SECURITY_LOG_DIR`: 監査ログ出力先を上書き
  - `CHAMELEON_ALLOWED_ORIGINS`: CORS許可リスト (カンマ区切りHTTPS URL)
  - `CHAMELEON_PERFORMANCE_MODE`: `core.py` のバッファ設定を調整

- **設定ファイル例**
  ```yaml
  id: secure_workflow
  tasks:
    - id: normalize_main
      function:
        type: builtin
        module: builtins
        name: len
      inputs:
        file: /absolute/path/input.wav
      dependencies: []
  ```

- **ログディレクトリ**: `.chameleon/logs/` が存在しない場合は手動で作成し、所有者のみ書き込み可能に設定します。

## 8. トラブルシューティング / Troubleshooting

- **File not found**: 絶対パスを使用しているか、`SecurityValidator.validate_file_path()` が拒否していないか確認。
- **URL rejected**: `validate_url()` がローカルまたはHTTPスキームを拒否していないか、`CHAMELEON_ALLOWED_ORIGINS` を確認。
- **Logging disabled**: `.chameleon/logs/` の権限 (POSIX 0750) と空き容量を確認。
- **Test failures**: `python -m unittest test_framework.SecurityTests` の出力を確認し、該当箇所を是正。

### ログ確認 / Log Review

- `~/.chameleon/logs/chameleon_security.log`
- `~/.chameleon/logs/enterprise_cli.log`
- `~/.chameleon/logs/api-audit.log`

## 9. サポート / Support

- 商用サポートは提供していません。改善点はリポジトリの Issue や Pull Request で共有してください。
- 運用手順や構成管理は組織のセキュリティポリシーに従ってください。

---

本マニュアルは安全な運用を目的とした最小限の構成を示します。追加の要件がある場合は、`security_validator.py` のポリシーを拡張し、テストと監査ログを必ず更新してください。
