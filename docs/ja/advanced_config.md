# 高度な設定

このドキュメントでは、Chameleon Audio Tool v1.0.0 で利用できる設定手段を説明します。設定を行わない場合は組み込みの既定値が使用されます。

## 環境変数

CLI は以下の環境変数を読み取り、既定値を上書きします。

- `CHAMELEON_PERFORMANCE_MODE`（`auto` / `fast` / `safe`）。チャンクサイズのプリセットを切り替えます。`fast` は既定値の 2 倍（上限 4 MiB）、`safe` は 1/2（下限 4 KiB）、`auto` は 64 KiB を使用します。
- `CHAMELEON_CHUNK_SIZE`（整数）。ストリーミング時のチャンクサイズ（バイト単位）を上書きします。4096〜4194304 の範囲外を指定した場合は既定値 65536 にフォールバックします。
- `CHAMELEON_MAX_WORKERS`（整数）。バッチ処理のワーカー数を制限します。既定値は `4` です。
- `CHAMELEON_BACKUP`（`true` / `false`。既定値は `true`）
- `CHAMELEON_TIMEOUT`（整数秒）。操作全体のタイムアウトを設定します。0 以下や整数以外を指定した場合は既定値 300 に戻ります。
- `CHAMELEON_LOG_LEVEL`（`DEBUG` / `INFO` など。既定値は `INFO`）
- `NO_COLOR`（`1` を指定するとカラー表示を無効化）

設定例:

```bash
export CHAMELEON_PERFORMANCE_MODE=fast
export CHAMELEON_MAX_WORKERS=2
export NO_COLOR=1
```

## JSON 設定ファイル

`~/.chameleon_audio_config.json`（またはカレントディレクトリの `chameleon_audio_config.json`）が存在すると、その内容で既定値を上書きします。ファイルは次のキーを持つ JSON オブジェクトです。

- `performance_mode`
- `max_workers`
- `chunk_size`
- `enable_colors`
- `log_level`
- `backup_enabled`
- `timeout_seconds`

例:

```json
{
  "performance_mode": "fast",
  "max_workers": 3,
  "chunk_size": 32768,
  "enable_colors": false,
  "log_level": "DEBUG",
  "backup_enabled": true,
  "timeout_seconds": 180
}
```

環境変数が設定されている場合は、JSON に記載された値よりも環境変数が優先されます。

## 設定の確認と管理

`config` サブコマンドで現在の設定を確認したり、ファイルに保存したりできます。

```bash
# 現在の設定を表示
chameleon config --show

# 設定を JSON として書き出し
chameleon config --export --output my_config.json

# 保存した JSON を読み込み
chameleon config --import --input my_config.json

# 既定値にリセット
chameleon config --reset
