# Chameleon Audio Tool コマンドリファレンス

## 概要

本ドキュメントは v1.0.0 で利用できるコマンドをまとめたものです。いずれも Python 標準ライブラリのみで実装されています。

## コアコマンド

### `analyze`

WAV ファイルの時間、チャンネル数、サンプルレート、フレーム数、サンプル幅、ピークレベルを表示します。

```
chameleon analyze input.wav
chameleon analyze input.wav --format json
```

主なオプション:

- `--format` : `text` / `json` / `csv` / `xml`（既定値 `text`）
- `--summary` : JSON 出力時に要約ファイルを生成

### `normalize`

0.0〜1.0 の範囲で指定したピーク値まで音量を正規化します。

```
chameleon normalize input.wav output.wav --target 0.90
```

主なオプション:

- `--target` : 目標ピーク値（既定値 `0.90`）
- `--auto-name` : 出力ファイル名を自動生成
- `--overwrite` : 既存ファイルを上書き

### `convert`

チャンネル数やサンプルレートのメタデータを変更します（再サンプリングは行いません）。

```
chameleon convert input.wav output.wav --mono --rate 44100
```

主なオプション:

- `--mono` : モノラルへダウンミックス
- `--rate` : サンプルレートのメタデータを設定

### `trim`

先頭と末尾の無音部分を除去し、必要に応じてパディングを残します。

```
chameleon trim input.wav output.wav --threshold 0.02 --min-silence 0.25
```

主なオプション:

- `--threshold` : 無音判定の閾値（0.0〜1.0、既定値 `0.02`）
- `--min-silence` : 残す無音パディング（秒、既定値 `0.25`）

### `check-duplicates`

事前に入力パスの重複を検査します。パスを正規化して参照の重複を報告し、重複がある場合はステータス `1` で終了します。

```
chameleon check-duplicates ./audio/a.wav ./audio/b.wav ./audio/a.wav
```

重複が検出されない場合は「No duplicate input paths detected」と表示し、ステータス `0` で終了します。

### `find-duplicates`

ファイルサイズとハッシュ値に基づいて重複 WAV を検出します。

```
chameleon find-duplicates ./audio --min-size 2048
```

主なオプション:

- `--min-size` : 対象とする最小ファイルサイズ（バイト、既定値 `1024`）

### `batch`

指定ディレクトリ配下の WAV を順次 `analyze` します。

```
chameleon batch ./audio --skip-errors
```

主なオプション:

- `--skip-errors` : 個別ファイルでエラーが発生しても処理を継続
- `--max-files` : 処理対象ファイル数の上限を指定

各ファイルの成否とリトライ回数、総リトライ数を表示します。`CHAMELEON_TIMEOUT` が動作中に経過した場合は、サマリでタイムアウト状況が明示されます。
## そのほかのコマンド

- メタデータ: `metadata`, `edit-metadata`
- 解析補助: `silence`, `vad`, `level-meter`, `quality-check`
- 効果/調整: `fade`, `noise-reduce`, `compress`, `auto-enhance`
- 補助ツール: `config`, `diagnostics`, `history`

詳細な使い方は `chameleon <command> --help` を参照してください。
