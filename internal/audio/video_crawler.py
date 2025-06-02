import argparse
import yt_dlp
import os
import yaml

# Function to load config.yaml
def load_config(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception:
        return {}

def validate_config(config):
    required = ['video_dir', 'python_path']
    missing = [k for k in required if not config.get(k)]
    if missing:
        exit(1)

import sys

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--lang', default=None, help='言語コード（例: ja, en, zh, etc）')
    parser.add_argument('--max', type=int, default=None, help='最大ダウンロード数')
    parser.add_argument('--outdir', default=None, help='保存先ディレクトリ')
    parser.add_argument('--url', default=None, help='任意のYouTube動画またはプレイリストURL')
    parser.add_argument('--config', default='config.yaml', help='設定ファイルパス')
    args = parser.parse_args()

    config = load_config(args.config)
    validate_config(config)
    lang = args.lang or config.get('lang', 'ja')
    max_dl = args.max if args.max is not None else config.get('max_download', 3)
    outdir = args.outdir or config.get('video_dir', 'data/videos')
    os.makedirs(outdir, exist_ok=True)

    # URL優先、なければ自動巡回
    if args.url:
        target = args.url
    else:
        query = f'おすすめ {lang} language'
        target = f"ytsearch{max_dl}:{query}"

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(outdir, '%(title)s.%(ext)s'),
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'writeinfojson': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([target])
    except Exception:
        sys.exit(1)

if __name__ == '__main__':
    main()
