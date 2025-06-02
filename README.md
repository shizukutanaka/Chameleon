# 軽量ボイスチェンジャー（Go実装）

## 概要
動画から音声を抽出し、声質・話し方を学習。プロンプト指定で任意の声・話し方を出力できる常駐型デスクトップアプリ。

## 構成
- main.go: エントリーポイント
- internal/audio: 音声抽出・処理
- internal/ui: 最小限のUI
- models/: 学習データ保存
- config.json: DiffusionモデルAPIサーバの設定

## 必要要件
- Go 1.20+
- Python 3.8+（librosa, numpy, soundfile, 必要なDiffusionモデル）
- FFmpeg（パスを通しておくこと）
- curl（APIリクエスト用）

## 完全ローカル・サーバーレス動作
- 本アプリは外部APIやネットワークを使わず、PC内で全て完結します。
- Diffusionモデル（so-vits-svc, Bark, StableTTS等）の推論は `internal/audio/diffusion_infer.py` を直接呼び出して実行します。

### モデルファイルの配置例
- `models/` ディレクトリに必要なモデル重みや設定ファイルを配置してください。
  - 例: `models/model.pth`, `models/config.json` など

### diffusion_infer.py の編集例
- 既定ではダミーwavを生成します。
- 実際の推論を行うには、so-vits-svcやBark等のCLI呼び出し部分（subprocess.runなど）を有効化してください。
- 詳細は `internal/audio/diffusion_infer.py` のコメントを参照。

---

## 使い方

### 1. 依存パッケージのインストール
- Python 3.8+
- Go 1.20+
- FFmpeg（パスを通す）
- 必要なPythonライブラリ: `pip install librosa numpy soundfile requests beautifulsoup4 yt-dlp pyyaml`
- Goライブラリ: `go get gopkg.in/yaml.v2`

### 2. 設定ファイル(config.yaml)で全て管理
- `config.yaml`で**全てのパス・動作パラメータを一元管理**できます
- 言語、保存先、学習間隔、モデルパス、ログファイルなどを自由にカスタマイズ可能
- Go/Pythonどちらから実行しても`--config`で同じ設定ファイルを参照

#### config.yaml例
```yaml
lang: ja
interval_min: 60
max_download: 3
video_dir: data/videos
mfcc_dir: data/mfcc
model_dir: models
voice_features_csv: models/voice_features.csv
people_metadata_csv: models/people_metadata.csv
python_path: python
extract_mfcc_py: internal/audio/extract_mfcc.py
extract_people_py: internal/audio/extract_people_info.py
diffusion_infer_py: internal/audio/diffusion_infer.py
video_crawler_py: internal/audio/video_crawler.py
log_file: error.log
log_level: info
```

### 3. 実行方法
- `go run main.go` またはビルドして実行
- CLIで言語や学習間隔を指定（config.yamlの値がデフォルト）
- バックグラウンドでYouTubeから音声収集→特徴量抽出→メタデータ抽出→モデル学習まで全自動

#### Pythonスクリプト単体で実行する場合も`--config`でパス・パラメータを完全同期
例: 
```sh
python internal/audio/video_crawler.py --config config.yaml
python internal/audio/extract_people_info.py --desc "説明文" --config config.yaml
python internal/audio/extract_mfcc.py --input foo.wav --output foo.csv --config config.yaml
```

### 4. カスタマイズ・環境切替も簡単
- `config.yaml`を複数用意し、`--config`で切り替えればOK

---

## 【新機能】自動学習サイクル・重複排除・進捗レポート

### 自動学習サイクル
- `main.go`がバックグラウンドで定期的に
  1. 動画/音声の自動収集
  2. MFCC特徴量抽出
  3. メタデータ抽出
  4. モデル学習
  を自動実行します（config.yamlの`interval_min`分ごと）。
- サイクルごとに進捗・エラーをCLIと`report_file`（例: `cycle_report.log`）に記録します。
- 失敗時は`retry_count`回まで自動リトライ。

### 重複排除（音声特徴量の多様性管理）
- `extract_mfcc.py`は、特徴量CSV（`voice_features_csv`）内の既存ベクトルとコサイン類似度を計算。
- `duplicate_threshold`（例: 0.95）以上の類似度があれば「重複」としてスキップし、無駄なデータ増加を防止。
- 新規データのみ特徴量CSVに自動追記。

### config.yamlの新パラメータ例
```yaml
retry_count: 3              # サイクル失敗時の最大リトライ回数
report_file: cycle_report.log # サイクルごとの進捗レポート出力先
duplicate_threshold: 0.95   # MFCC類似度による重複判定閾値
```

### 運用例
- `go run main.go` を起動しておくだけで、全自動でデータ収集・学習・品質管理が進みます。
- 進捗やエラーはCLIと`cycle_report.log`、詳細エラーは`error.log`で確認可能。
- 特徴量の重複排除により、データの多様性・品質を自動で担保します。

### 注意事項
- `voice_features_csv`や`people_metadata_csv`は自動で追記・管理されます。
- サイクル間隔やリトライ回数などは`config.yaml`で柔軟に調整可能。
- さらに通知機能や多様な拡張も今後容易に追加できます。
- 例: `python ... --config config_prod.yaml` など

---

## Author

- Name: Shizuku Tanaka
- GitHub: [shizukutanaka](https://github.com/shizukutanaka)

## Donate

If you would like to support development, donations are welcome!
- BTC: 1GzHriuokSrZYAZEEWoL7eeCCXsX3WyLHa
