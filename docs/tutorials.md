# Chameleon Audio Processor - チュートリアルガイド / Tutorial Guide

## 1. CLI 基本操作 / CLI Essentials

- **目的**: 決定論的CLIを安全に実行する
- **手順**
  ```bash
  # 入力ファイルのドライラン検証
  python chameleon_cli.py analyze /absolute/path/input.wav --dry-run --json

  # 実処理（正規化）
  python chameleon_cli.py process --normalize /absolute/path/input.wav --output-dir=/absolute/path/output

  # 監査ログ確認
  tail -n 20 ~/.chameleon/logs/chameleon_security.log
  ```

## 2. Enterprise CLI ワークフロー / Enterprise CLI Workflow

- **目的**: `enterprise_cli.py` でバッチ処理を安全に実行
- **手順**
  ```bash
  # ディレクトリ検証のみ
  python enterprise_cli.py batch-process --directory /absolute/path/incoming --dry-run

  # 正規化処理を実行
  python enterprise_cli.py batch-process --directory /absolute/path/incoming --operation normalize

  # ログレビュー
  tail -n 20 ~/.chameleon/logs/enterprise_cli.log
  ```

## 3. バッチ自動化 / Batch Automation

- **目的**: `batch_automation.py` で設定ファイル駆動のワークフローを構築
- **設定例**
  ```yaml
  id: nightly_normalize
  tasks:
    - id: normalize_all
      function:
        type: script
        path: /absolute/path/scripts/normalize.py
      inputs:
        directory: /absolute/path/input
      dependencies: []
  ```
- **実行手順**
  ```python
  from batch_automation import BatchAutomation

  automation = BatchAutomation()
  workflow = automation.create_workflow("/absolute/path/nightly.yaml")
  automation.execute(workflow.id)
  ```

## 4. API サーバー / API Server

- **目的**: `api_server.py` を HTTPS 経由で利用
  ```bash
  uvicorn api_server:app --host 127.0.0.1 --port 8443
  ```
- **API呼び出し例**
  ```python
  import os
  import requests

  base_url = os.environ["CHAMELEON_BASE_URL"]  # 例: https://audio.example.org/chameleon
  token = os.environ["CHAMELEON_API_TOKEN"]
  headers = {"Authorization": f"Bearer {token}"}

  response = requests.post(
      f"{base_url}/audio/analyze",
      json={"file_name": "/absolute/path/input.wav"},
      timeout=30
  )
  response.raise_for_status()
  ```

## 5. URL 検証 / URL Validation

- **目的**: 外部URLを事前審査
  ```python
  import os
  from security_validator import SecurityValidator

  validator = SecurityValidator()
  secure_url = validator.validate_url(
      os.environ["CHAMELEON_ASSET_URL"],
      allowed_schemes={"https"},
      allow_localhost=False
  )
  ```
- `SecurityError` が発生した場合はURLが許可されていません。

## 7. テストと検証 / Testing & Validation

- **単体テスト**
  ```bash
  python -m unittest test_framework.SecurityTests
  ```
- **包括テスト**
  ```bash
  python test_framework.py
  ```
- **CI統合**: Pull Request 時に上記テストを実行し、結果を監査ログとともに保存します。

## 8. 運用ベストプラクティス / Operational Best Practices

- **絶対パスの使用**: CLI引数や設定ファイルのパスは `/` から始まる完全修飾パスを指定
- **URLホワイトリスト**: `CHAMELEON_ALLOWED_ORIGINS` で許可するドメインを明示し、`validate_url()` と整合させる
- **ディレクトリ権限**: `.chameleon/logs/` は所有者のみが書き込み可能 (POSIX 0750) に設定
- **ローテーション監視**: `chameleon_security.log` と `api-audit.log` のサイズ・世代が想定どおりか定期確認
- **テスト更新**: セキュリティポリシー変更時は `test_framework.SecurityTests` を拡張し、カバレッジを確保

---

このドキュメントはGUI操作や非決定的ワークフローではなく、絶対パス・HTTPS・監査ログを前提としたCLI/バッチ運用に焦点を当てています。すべてのURL・パス・ディレクトリは `SecurityValidator` を通じて検証し、国家レベルの運用が可能な構成を維持してください。
