import sys
import numpy as np
import librosa
import soundfile as sf
import argparse
import csv
import yaml

# config.yamlを読み込む関数
def load_config(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception:
        return {}

def validate_config(config):
    required = ['mfcc_dir', 'python_path']
    missing = [k for k in required if not config.get(k)]
    if missing:
        exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--config', default='config.yaml')
    args = parser.parse_args()

    config = load_config(args.config)
    validate_config(config)
    duplicate_threshold = float(config.get('duplicate_threshold', 0.95))
    features_csv = config.get('voice_features_csv', 'voice_features.csv')

    y, sr = librosa.load(args.input, sr=None)
    mfcc = librosa.feature.mfcc(y, sr=sr, n_mfcc=20)
    mfcc_mean = np.mean(mfcc, axis=1)

    # --- 重複判定 ---
    import os
    def cosine_similarity(a, b):
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
    is_duplicate = False
    if os.path.exists(features_csv):
        with open(features_csv, 'r', newline='') as f:
            reader = csv.reader(f)
            header = next(reader, None)
            for row in reader:
                try:
                    vec = np.array([float(x) for x in row])
                    sim = cosine_similarity(mfcc_mean, vec)
                    if sim >= duplicate_threshold:
                        is_duplicate = True
                        break
                except Exception:
                    continue
    if is_duplicate:
        sys.exit(0)

    # --- MFCC出力 ---
    with open(args.output, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([f"mfcc{i+1}" for i in range(len(mfcc_mean))])
        writer.writerow(mfcc_mean)

    # --- voice_features_csvに追記 ---
    with open(features_csv, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(mfcc_mean)
