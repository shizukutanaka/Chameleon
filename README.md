# Chameleon: 軽量ボイスチェンジャー & 音声変換プラットフォーム

## 概要
Chameleonは、音声・動画から多様な声質・話し方を学習し、任意の声で音声変換（Voice Changer）を行うデスクトップアプリです。完全ローカル動作・高い拡張性・直感的なGUIモデル管理を特徴とします。

---

## 主な特徴
- **完全ローカル動作**（外部API不要、個人情報も安心）
- **Python & Goハイブリッド**（CLI/GUI両対応）
- **多様なOSS音声変換モデル対応**（so-vits-svc, RVC, Bark, StableTTS等）
- **モデル管理・メタデータ編集GUI**（有効/無効・タグ・説明・バージョン等を即編集）
- **バッチ変換・マイク変換・進捗自動レポート**
- **高品質な重複排除・データ多様性管理**

---

## ディレクトリ構成
- `main.go` : エントリーポイント
- `internal/audio/` : 音声抽出・変換・特徴量処理
- `internal/ui/` : PyQt5ベースのGUI（モデル管理含む）
- `voice_models/` : 学習済み音声モデル（各モデルごとにサブディレクトリ＋メタデータ）
- `models/` : OSS音声変換モデル本体や重み
- `config.yaml` : 全体設定ファイル

---

## 必要要件・推奨依存パッケージ
- **Go 1.20+**
- **Python 3.8+**
- **FFmpeg**（パスを通す）
- **推奨Pythonパッケージ**:
  ```sh
  pip install librosa numpy soundfile requests beautifulsoup4 yt-dlp pyyaml PyQt5
  ```
- **Goライブラリ**:
  ```sh
  go get gopkg.in/yaml.v2
  ```

---

## セットアップ・基本的な使い方

### 1. 依存パッケージをインストール
- 上記のPython/Goパッケージ・FFmpegを導入

### 2. 設定ファイル（config.yaml）を編集
- 主要なパス・パラメータを一元管理
- 例:
  ```yaml
  lang: ja
  interval_min: 60
  model_dir: models
  voice_models_dir: voice_models
  ...
  ```

### 3. モデルファイル・メタデータの配置
- `voice_models/モデル名/` ディレクトリを作成し、`model_info.json`（下記参照）を配置
- OSS音声変換モデル（so-vits-svc等）は`models/`配下に設置

### 4. 実行
- Go: `go run main.go` またはビルドして実行
- Python: 各種スクリプトを直接実行
- GUI: `python internal/ui/voice_changer_gui.py`

---

## モデル管理・メタデータ編集GUI

### 概要
ChameleonのGUIでは、各音声モデルの詳細（表示名・バージョン・説明・タグ・有効/無効等）を直感的に管理できます。

### 使い方
1. **「モデル管理」ボタン**をクリック
   - モデルごとに有効/無効や説明・タグ等を編集できるダイアログが開きます。
2. **編集内容を保存**
   - `voice_models/モデル名/model_info.json`に即時反映されます。
3. **有効モデルのみが変換先・バッチ変換で選択可能**
   - 無効化したモデルはリストから除外されます。

### メタデータJSON例
```json
{
  "name": "sample_model",
  "display_name": "サンプルモデル",
  "description": "デモ用のボイスチェンジャーモデル。高音質・高速推論対応。",
  "version": "1.0.0",
  "author": "Chameleon Dev Team",
  "created_at": "2025-06-06",
  "tags": ["demo", "high-quality", "fast"],
  "enabled": true
}
```

#### 注意点
- `voice_models/`配下に必ずモデルごとのディレクトリ＋`model_info.json`を用意してください
- メタデータ編集後は「保存」を忘れずに
- モデル追加・削除や詳細編集もGUIから順次サポート予定

---

## よくある質問・トラブルシュート
- **yt-dlp関連エラー**: `pip install yt-dlp` で解決
- **モデルが選択肢に出ない**: `model_info.json`の`enabled`が`true`か、ファイル/ディレクトリ名のスペルを確認
- **GUIが起動しない**: `pip install PyQt5` を確認
- **音声変換が遅い/失敗する**: GPU推奨、OSS本体のセットアップ手順も要確認

---

## 開発・拡張
- モデル追加・削除・検索・タグフィルタなどGUI機能を今後も拡張予定
- メタデータスキーマやAPI連携も柔軟に拡張可能
- PR・issue歓迎

---

## Author
- Name: Shizuku Tanaka
- GitHub: [shizukutanaka](https://github.com/shizukutanaka)

## Donate
If you would like to support development, donations are welcome!
- BTC: 1GzHriuokSrZYAZEEWoL7eeCCXsX3WyLHa

## マイク音声のワンストップ変換機能

- `internal/audio/mic2vc.py` を使うことで、マイクから録音した音声を「学習済みの声」にワンストップで変換・再生できます。
- 低遅延かつローカル完結で動作します。

### 使い方（コマンド例）
```sh
python internal/audio/mic2vc.py --target_voice モデル名 --duration 5
```
- `--target_voice` … 変換先の声モデル名（voice_models/配下に保存）
- `--duration` … 録音時間（秒、デフォルト5秒）

録音→変換→再生まで自動で行われます。

### 必要要件
- Pythonパッケージ: sounddevice, soundfile
- so-vits-svcやRVC等の音声変換モデル本体と学習済みモデル

### カスタマイズ例
- `--samplerate`, `--channels`, `--tmp_dir` などで詳細な録音・変換設定が可能

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

---

## 【新機能】ボイスチェンジャー（音声変換）

Chameleonで収集・学習した音声データを元に、任意の音声ファイルを「学習済みの声」に変換できるボイスチェンジャー機能を追加しました。

### 必要なもの
- so-vits-svc や RVC などのオープンソース音声変換ツール（別途セットアップが必要）
- `voice_models/` ディレクトリに変換先の声モデル（学習済みモデル）を保存

### 使い方（コマンドライン例）
```sh
python internal/audio/voice_changer.py --input 入力音声.wav --target_voice モデル名 --output 出力.wav
```
- `--input`: 変換したい音声ファイル（wav, mp3等）
- `--target_voice`: 変換先の声モデル名（`voice_models/` 配下に保存）
- `--output`: 変換後の音声ファイル名

### マイク音声の変換（ワンストップ）

マイクから直接録音した音声を「学習済みの声」に変換し、そのまま再生できます。

```sh
python internal/audio/mic2vc.py --target_voice モデル名 --duration 5
```
- `--target_voice`: 変換先の声モデル名
- `--duration`: 録音時間（秒、デフォルト5秒）

録音→変換→再生まで自動で行われます。

### モデルの作成方法
- Chameleonで収集した音声データをso-vits-svcやRVC等のOSSに渡して学習し、`voice_models/`に保存してください。
- 詳細な手順は各OSSのREADMEを参照してください。

### 注意事項
- モデルの学習や音声変換にはGPUが推奨されます。
- OSS本体のセットアップは各プロジェクトの手順に従ってください。


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

## モデル管理・メタデータ編集機能

ChameleonのGUIでは、各音声モデルの詳細情報（表示名・バージョン・説明・タグ・有効/無効など）を直感的に管理できます。

### 使い方

1. **「モデル管理」ボタン**をクリック  
   → モデルごとに有効/無効や説明・タグ等を編集可能なダイアログが開きます。
2. **編集内容を保存**  
   → `voice_models/モデル名/model_info.json`に即時反映されます。
3. **有効モデルのみが変換先・バッチ変換で選択可能**  
   → 無効化したモデルはリストから除外されます。

### メタデータ例
```json
{
  "name": "sample_model",
  "display_name": "サンプルモデル",
  "description": "デモ用のボイスチェンジャーモデル。高音質・高速推論対応。",
  "version": "1.0.0",
  "author": "Chameleon Dev Team",
  "created_at": "2025-06-06",
  "tags": ["demo", "high-quality", "fast"],
  "enabled": true
}
```

### 注意点
- `voice_models/`配下にモデルごとのディレクトリと`model_info.json`を用意してください。
- メタデータ編集後は「保存」を忘れずに。
- モデル追加・削除や詳細編集もGUIから順次サポート予定です。

---

## Author

- Name: Shizuku Tanaka
- GitHub: [shizukutanaka](https://github.com/shizukutanaka)

## Donate

If you would like to support development, donations are welcome!
- BTC: 1GzHriuokSrZYAZEEWoL7eeCCXsX3WyLHa
