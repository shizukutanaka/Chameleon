# Lightweight Voice Changer (Go Implementation)

## Overview
A fully automated, lightweight, and silent desktop app that extracts audio from videos, learns voice features and speaking style, and outputs any desired voice or style via prompt specification.

## Structure
- main.go: Entry point
- internal/audio: Audio extraction and processing
- internal/ui: Minimal UI (optional)
- models/: Stores learning data
- config.yaml: Unified configuration for all modules

## Requirements
- Go 1.20+
- Python 3.8+ (librosa, numpy, soundfile, yt-dlp, requests, beautifulsoup4, pyyaml)
- FFmpeg (must be in PATH)

## Fully Local & Serverless
- No external APIs or network access required. All processing is done locally.
- Diffusion model inference (so-vits-svc, Bark, StableTTS, etc.) is called via `internal/audio/diffusion_infer.py`.

### Model File Placement Example
- Place model weights/configs in the `models/` directory.
  - Example: `models/model.pth`, `models/config.json`, etc.

### Editing diffusion_infer.py
- By default, generates a dummy wav file.
- To use real inference, enable the CLI call to so-vits-svc, Bark, etc. (see comments in the script).

---

## Usage

### 1. Install Dependencies
- Python 3.8+
- Go 1.20+
- FFmpeg (add to PATH)
- Python: `pip install librosa numpy soundfile requests beautifulsoup4 yt-dlp pyyaml`
- Go: `go get gopkg.in/yaml.v2`

### 2. Unified Configuration (`config.yaml`)
- All paths and parameters are managed in `config.yaml`.
- Language, directories, learning interval, model paths, log files, etc. are customizable.
- Both Go and Python scripts use the same config file via `--config`.

#### Example config.yaml
```yaml
lang: en
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
```

### 3. Run
- `go run main.go` or build and execute
- CLI options can override config.yaml defaults
- YouTube audio collection → feature extraction → metadata extraction → model learning, all fully automated

#### To run Python scripts directly:
```sh
python internal/audio/video_crawler.py --config config.yaml
python internal/audio/extract_people_info.py --desc "Description" --config config.yaml
python internal/audio/extract_mfcc.py --input foo.wav --output foo.csv --config config.yaml
```

### 4. Easy Customization & Environment Switching
- Use multiple config.yaml files and switch with `--config`

---

## [NEW] Automated Learning Cycle, Duplicate Removal, Progress Report

### Automated Learning Cycle
- `main.go` runs periodically in the background:
  1. Automatic video/audio collection
  2. MFCC feature extraction
  3. Metadata extraction
  4. Model learning
- The cycle interval is set by `interval_min` in config.yaml.
- Progress and errors are logged to CLI and `cycle_report.log`.
- Automatic retry up to `retry_count` times on failure.

### Duplicate Removal (Feature Diversity Management)
- `extract_mfcc.py` calculates cosine similarity with existing vectors in `voice_features_csv`.
- If similarity exceeds `duplicate_threshold` (e.g. 0.95), the data is skipped as duplicate.
- Only new, diverse data is appended to the CSV.

### Example config.yaml parameters
```yaml
retry_count: 3              # Max retries per cycle
report_file: cycle_report.log # Progress report file
duplicate_threshold: 0.95   # Cosine similarity threshold for duplicates
```

### Operation Example
- Just run `go run main.go` for fully automated data collection, learning, and quality control.
- Progress/errors are logged to CLI and `cycle_report.log`, detailed errors to `error.log`.
- Duplicate removal ensures data diversity and quality.

### Notes
- `voice_features_csv` and `people_metadata_csv` are managed and appended automatically.
- Cycle interval, retry count, etc. are configurable in `config.yaml`.
- Notification features and further extensions can be easily added.
- Example: `python ... --config config_prod.yaml`

---

## Author

- Name: Shizuku Tanaka
- GitHub: [shizukutanaka](https://github.com/shizukutanaka)

## Donate

If you would like to support development, donations are welcome!
- BTC: 1GzHriuokSrZYAZEEWoL7eeCCXsX3WyLHa
