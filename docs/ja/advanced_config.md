# 高度な設定

Chameleon の設定は**環境変数**とコマンドラインフラグのみで行います。
設定ファイルも `config` サブコマンドも存在しません。以下の変数はすべて、
実際にそれを読み取っているコードと突合して検証済みです。

## 環境変数

| 変数 | 読み取り元 | 効果 |
|------|-----------|------|
| `CHAMELEON_PERFORMANCE_MODE` | `core.py` | `auto`（既定）/ `fast` / `safe`。`fast` は既定チャンクサイズを2倍（上限 4 MiB）、`safe` は半分（下限 4 KiB）、`auto` は既定の 64 KiB を維持。 |
| `CHAMELEON_CHUNK_SIZE` | `core.py` | チャンクサイズ（バイト）。4096〜4194304 の範囲外は既定の 65536 にフォールバック。パフォーマンスモードの設定より優先されます。 |
| `CHAMELEON_TIMEOUT` | `core.py` | 長時間バッチ処理の上限時間（秒）。 |
| `CHAMELEON_STATE_DIR` | `core.py` | バッチ状態ファイルの保存先ディレクトリ。既定はユーザーごとの場所。 |
| `CHAMELEON_MAX_WORKERS` | `main.py` | バッチ処理のワーカー数。数値でない値は無視されます。 |
| `CHAMELEON_PARALLEL` | `main.py` | `0` / `false` / `off` / `no` のいずれかで並列実行を無効化。それ以外の値は有効。 |
| `CHAMELEON_LOG_DIR` | `main.py` | ログ出力先。既定は `~/.chameleon/logs`（POSIX では `0700` で作成）。 |

```bash
export CHAMELEON_PERFORMANCE_MODE=fast
export CHAMELEON_MAX_WORKERS=2
chameleon batch ./audio normalize --output-dir out/
```

## コマンドラインでの指定

上記のうち2つはグローバルフラグを持ち、その実行に限り環境変数より優先されます。

```bash
chameleon --max-workers 4 batch ./audio normalize --output-dir out/
chameleon --no-parallel  batch ./audio normalize --output-dir out/
```

## 値の検証動作

値は読み取り時に検証されます。整数として不正な値や許容範囲外の値は、例外を
送出せず既定値にフォールバックします。つまり設定の打ち間違いは性能設定に
影響するだけで、処理そのものは止まりません。

## 意図的に存在しないもの

- **設定ファイルはありません。** `main.py` / `core.py` は JSON・YAML・INI の
  いずれの設定ファイルも読み込みません。設定は環境変数とフラグのみです。
- **`config` サブコマンドはありません。** 値の確認・設定には `env` / `export`
  を使ってください。

`personal_config.py` は個人利用向けヘルパー用に独自の JSON ファイルを持ちますが、
これは単独スクリプトであり、CLI の設定には影響しません。
