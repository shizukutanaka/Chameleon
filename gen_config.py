import yaml

DEFAULT_CONFIG = {
    'lang': 'ja',
    'interval_min': 60,
    'max_download': 3,
    'video_dir': 'data/videos',
    'mfcc_dir': 'data/mfcc',
    'model_dir': 'models',
    'voice_features_csv': 'models/voice_features.csv',
    'people_metadata_csv': 'models/people_metadata.csv',
    'python_path': 'python',
    'extract_mfcc_py': 'internal/audio/extract_mfcc.py',
    'extract_people_py': 'internal/audio/extract_people_info.py',
    'diffusion_infer_py': 'internal/audio/diffusion_infer.py',
    'video_crawler_py': 'internal/audio/video_crawler.py',
    'log_file': 'error.log',
    'log_level': 'info',
}

def main():
    with open('config.yaml', 'w', encoding='utf-8') as f:
        yaml.dump(DEFAULT_CONFIG, f, allow_unicode=True, sort_keys=False)
    print('config.yaml (サンプル) を生成しました')

if __name__ == '__main__':
    main()
