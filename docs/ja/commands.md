# Chameleon Audio Tool コマンドリファレンス

本ドキュメントの全コマンド・全オプションは `main.py --help` と実際の実行で
検証済みです（v1.1.0）。ここに書かれている内容を CLI が受け付けない場合、
それは本ドキュメントのバグですのでご報告ください。

`python main.py <command>` または `pip install -e .` 後に
`chameleon <command>` として実行します。

```
chameleon [--version] [--max-workers N] [--no-parallel]
          {analyze,process,stream,batch,ml,midi,plugins,server} ...
```

グローバルオプション:

| オプション | 意味 |
|-----------|------|
| `--version` | バージョンを表示して終了 |
| `--max-workers N` | バッチ処理のワーカースレッド数を制限 |
| `--no-parallel` | 並列実行を無効化 |

---

## コアコマンド（標準ライブラリのみで動作）

### `analyze`

音声ファイルを解析します。

```bash
chameleon analyze input.wav
chameleon analyze input.wav --detailed
chameleon analyze *.wav --export report.json
chameleon analyze input.wav --spectrum
chameleon analyze input.wav --loudness
```

| オプション | 意味 |
|-----------|------|
| `--detailed` | 詳細解析を表示 |
| `--export FILE` | 解析結果を JSON ファイルに出力 |
| `--spectrum` | 主要周波数・帯域幅・RMS も報告（標準ライブラリのみ・決定論的） |
| `--loudness` | ラウドネス計測も報告（標準ライブラリのみ）— 下記参照 |

`--loudness` はファイル先頭の一定長を対象に以下を報告します:

- **Integrated loudness (LUFS)** — ITU-R BS.1770 K-weighting・ゲート付き。
  モノラル/ステレオではチャンネルのエネルギーを正しく合算します
  （サラウンドのチャンネル重み付けは未実装）。
- **True Peak (dBTP)** — 4倍オーバーサンプリングによるインターサンプルピーク
  推定値（BS.1770-4 Annex 2 方式）。
- **Max Momentary (LUFS)** — 400ms 窓の最大値、ゲートなし（EBU Mode）。
- **Max Short-term (LUFS)** — 3秒 窓の最大値、ゲートなし（EBU Mode）。
- **Loudness Range (LU)** — EBU Tech 3342。ゲート後の短期ラウドネスの
  95パーセンタイル − 10パーセンタイル。大きい部分と小さい部分がどれだけ
  離れているかを表します。本コマンドは先頭の一定長のみを解析するため、
  Tech 3342 が「安定」とみなす 60 秒に満たない場合はその旨も表示します。

いずれも正直に範囲を限定した測定値であり、認証されたラウドネスメーターでは
ありません。各主張の正確な範囲は `bs1770_loudness.py` の docstring を参照。

### `process`

ファイルを処理します。複数の操作を組み合わせ可能で、出力は `--output-dir`
（省略時は入力と同じ場所）に書き出されます。

```bash
# 正規化
chameleon process input.wav --normalize --target-peak 0.90 --output-dir out/

# ノイズ除去
chameleon process input.wav --denoise --output-dir out/

# サンプルレート・ビット深度の変換
chameleon process input.wav --convert --convert-sample-rate 44100 \
    --convert-bit-depth 16 --output-dir out/

# 書き込まずに動作を確認
chameleon process input.wav --normalize --dry-run

# 機械可読な出力
chameleon process input.wav --normalize --json
```

| オプション | 意味 |
|-----------|------|
| `--normalize` | 音量を正規化 |
| `--target-peak F` | `--normalize` の目標ピーク値 0.0〜1.0（既定 0.95） |
| `--denoise` | ノイズ除去 |
| `--master {default,streaming,cd,vinyl}` | マスタリングチェーン（EQ/コンプ/リミッタ/ラウドネス）。numpy 必須、scipy 推奨 |
| `--effects FILE` | JSON ファイルからエフェクトを適用 |
| `--convert` | フォーマット・解像度を変換 |
| `--convert-format FMT` | 変換先フォーマット（現在 `wav` のみ） |
| `--convert-sample-rate N` | 変換先サンプルレート |
| `--convert-bit-depth {16,24,32}` | 変換先ビット深度 |
| `--output-dir DIR` | 出力ディレクトリ |
| `--dry-run` | 書き込まずに予定操作を表示 |
| `--json` | 構造化 JSON で結果を出力 |

### `batch`

ディレクトリ内の全音声ファイルに単一の操作を適用します。

```bash
chameleon batch ./audio analyze
chameleon batch ./audio normalize --target-peak 0.9 --output-dir out/
chameleon batch ./audio convert --sample-rate 44100 --bit-depth 16 --output-dir out/
chameleon batch ./audio denoise --recursive --output-dir out/
```

位置引数: `directory` と
`{analyze, normalize, denoise, convert, effects}` のいずれか。

| オプション | 意味 |
|-----------|------|
| `--recursive` | サブディレクトリも処理 |
| `--output-dir DIR` | 出力ディレクトリ |
| `--format FMT` | 出力フォーマット |
| `--quality {low,medium,high,lossless}` | 出力品質 |
| `--target-peak F` | `normalize` 操作の目標ピーク値 |
| `--sample-rate N` | `convert` の変換先サンプルレート |
| `--bit-depth {16,24,32}` | `convert` の変換先ビット深度 |
| `--effects FILE` | `effects` 操作の設定ファイル |

### `midi`

MIDI 解析・作曲（純粋な標準ライブラリ実装）。

```bash
chameleon midi extract --input song.wav --output song.mid
chameleon midi analyze --input song.wav
chameleon midi compose --key C --mode major --tempo 120 --length 30 --output out.mid
chameleon midi generate --key G --mode minor --output out.mid
```

位置引数: `{extract, analyze, compose, generate}` のいずれか。

| オプション | 意味 |
|-----------|------|
| `--input FILE` | 入力音声ファイル |
| `--output FILE` | 出力 MIDI ファイル |
| `--key K` | 調（例: `C`, `G`, `F#`） |
| `--mode {major,minor}` | 旋法 |
| `--tempo N` | テンポ (BPM) |
| `--length N` | 長さ（秒） |

### `plugins`

プラグインの一覧表示と監査。

```bash
chameleon plugins list
chameleon plugins audit
chameleon plugins list --directory /abs/path/to/plugins --json
```

サブコマンド: `list`（検出されたプラグインとメタデータ）、
`audit`（サンドボックス適合性の検査）。

| オプション | 意味 |
|-----------|------|
| `--directory DIR` | 検査対象の絶対パス（複数指定可） |
| `--json` | 構造化 JSON で出力 |

---

## オプション依存パッケージが必要なコマンド

以下は依存ゼロの既定インストールでは動作しません。先に該当する extra を
インストールしてください（`README.md` 参照）。

### `ml` — numpy/scipy が必要

ノイズ除去と正規化による音質改善。

```bash
pip install -e .[audio]
chameleon ml enhance --input noisy.wav --output clean.wav
```

位置引数: `enhance`。オプション: `--input FILE`（必須）、`--output FILE`。

> 名称に関する注記: このサブコマンドが行うのは従来型の DSP（ノイズ除去と
> 正規化）です。機械学習は行いません（`CHARTER.md` §4 を参照）。

### `stream` — pyaudio が必要

リアルタイム音声処理。

```bash
pip install -e .[audio]
chameleon stream --input-device 1 --output-device 2 --effects effects.json
```

| オプション | 意味 |
|-----------|------|
| `--input-device N` | 入力デバイス番号 |
| `--output-device N` | 出力デバイス番号 |
| `--effects FILE` | エフェクト設定 (JSON) |

### `server` — fastapi/uvicorn が必要

ローカル REST API アダプタを起動します。

```bash
pip install -e .[api]
chameleon server --host 127.0.0.1 --port 8000 --workers 1
```

| オプション | 意味 |
|-----------|------|
| `--host H` | ホスト |
| `--port P` | ポート |
| `--workers N` | ワーカー数 |

この API は同じ標準ライブラリコアに対する薄い認証付きアダプタであり、
ホスティングサービスや別製品ではありません（`CHARTER.md` §3, §7）。

---

## 終了コード

`chameleon` は成功時に `0`、失敗時に非ゼロを返すため、シェルや CI の
パイプラインで利用できます。

```bash
if chameleon analyze input.wav; then
    echo "成功"
else
    echo "失敗 (コード $?)"
fi
```

---

## 対応範囲

本ツールは既定では WAV に特化しています。MP3/FLAC/OGG の入力は `[audio]`
extra をインストールした場合のみ動作し、コアの解析・正規化・バッチ・MIDI の
各処理は意図的にサードパーティ製パッケージなしで動作します。
スコープと非目標の全文は `CHARTER.md` を参照してください。
