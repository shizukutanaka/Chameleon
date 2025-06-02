import argparse
import numpy as np
import librosa
import sys
import yaml

def load_config(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception:
        return {}

def calc_mfcc_distance(ref_wav, gen_wav, n_mfcc=20):
    y1, sr1 = librosa.load(ref_wav, sr=None)
    y2, sr2 = librosa.load(gen_wav, sr=None)
    mfcc1 = np.mean(librosa.feature.mfcc(y1, sr=sr1, n_mfcc=n_mfcc), axis=1)
    mfcc2 = np.mean(librosa.feature.mfcc(y2, sr=sr2, n_mfcc=n_mfcc), axis=1)
    # コサイン距離
    cos_dist = 1.0 - np.dot(mfcc1, mfcc2) / (np.linalg.norm(mfcc1) * np.linalg.norm(mfcc2))
    # ユークリッド距離
    l2_dist = np.linalg.norm(mfcc1 - mfcc2)
    return cos_dist, l2_dist

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--ref', required=True, help='元音声wav')
    parser.add_argument('--gen', required=True, help='生成音声wav')
    parser.add_argument('--config', default='config.yaml')
    args = parser.parse_args()
    config = load_config(args.config)
    try:
        cos_dist, l2_dist = calc_mfcc_distance(args.ref, args.gen)
        sys.exit(0)
    except Exception:
        sys.exit(1)
