# テストガイド

## 概要

Chameleon Audio Tool v1.0.0 には組み込みのテストハーネスは含まれていません。本ガイドでは、現行の軽量 CLI に対して Python 標準ライブラリや `pytest` で実施できる現実的な検証ポイントをまとめます。

## 推奨ユニットテスト

- `_validate_input_safety()` に対するトラバーサル入力（例: `../danger.wav`）を確認し、`path_safe=False` と警告メッセージが返ることを検証する。
- `_load_config()` に壊れた JSON や欠落キーを渡し、デフォルトへ復元されること、および正しい上書き設定が読み込まれることを確認する。
- `_get_process_metrics()` が `psutil` 未導入時には `None` を返し、導入済み環境では `rss_mb` や `cpu_percent` を含む辞書を返すことを確認する。

例（pytest）:

```python
from audio_tool import _validate_input_safety

def test_validate_input_safety_rejects_relative(tmp_path):
    unsafe = tmp_path / ".." / "clip.wav"
    result = _validate_input_safety(unsafe)
    assert result["path_safe"] is False
    assert any("relative" in message for message in result["warnings"])
```

## 推奨統合テスト

- `python audio_tool.py analyze sample.wav --format json` を実行し、出力 JSON に `duration_seconds` と `channels` が含まれることを確認します。
- 複数の WAV ファイルを含む一時ディレクトリを用意し、`batch` コマンドを `--skip-errors` と共に実行して成功・失敗件数が期待通りに集計されることを確認します。
- `normalize` を `--overwrite` なしで実行して安全な失敗動作を確認し、続けて `CHAMELEON_BACKUP=true` と `--overwrite` を指定して `.backup` ファイルが生成されることを確認します。

## ドキュメントのスモークテスト

- `docs/ja/commands.md` に掲載されている各コマンドで `--help` を実行し、表示内容が記述と一致しているか確認します。
- `docs/ja/advanced_config.md` の JSON 例を `_load_config()` で読み込み、説明通りに優先順位と上書きが適用されることを確認します。

## テストの実行方法

- 代表的な実行コマンド: `python -m pytest tests/`
- 簡易な確認: `python -m unittest discover tests`
- 音声フィクスチャは 1 MB 未満に抑えてリポジトリを軽量に保ちます。

## フィクスチャ管理のヒント

- `tmp_path` や `TemporaryDirectory` を利用して WAV ファイルをテストごとに生成し、終了後に削除します。
- 再実行性を確保するため一時ディレクトリや生成物を必ずクリーンアップします。

## オプションツール

- `pytest-cov` でカバレッジを計測できますが必須ではありません。
- `ruff` や `bandit` などの静的解析ツールは必要に応じて導入してください。

テスト戦略は `audio_tool.py` の拡張に合わせて段階的に強化し、依存を最小限に抑えながら短時間で実行できる検証を優先してください。
