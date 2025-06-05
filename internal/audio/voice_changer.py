import argparse
import os
import subprocess

# このスクリプトはso-vits-svcやRVCなどの外部ボイスチェンジャーを呼び出すラッパー例です。
# 事前にvoiceモデルをvoice_models/ディレクトリ等に用意してください。

def main():
    parser = argparse.ArgumentParser(description='任意の声に変換するボイスチェンジャー')
    parser.add_argument('--input', required=True, help='変換したい音声ファイル（wav, mp3等）')
    parser.add_argument('--target_voice', required=True, help='変換先の声モデル名（例: user1, idol, etc）')
    parser.add_argument('--output', required=True, help='出力先ファイル名')
    parser.add_argument('--svc_root', default='so-vits-svc', help='so-vits-svc等のルートパス')
    args = parser.parse_args()

    # ここでは so-vits-svc の推論コマンドを例示
    # 実際のコマンドは利用OSSのREADMEに従って修正してください
    model_path = os.path.join('voice_models', args.target_voice)
    if not os.path.exists(model_path):
        raise FileNotFoundError(f'声モデルが見つかりません: {model_path}')

    # 例: so-vits-svc推論コマンド
    cmd = [
        'python', os.path.join(args.svc_root, 'inference_main.py'),
        '-m', model_path,
        '-c', os.path.join(model_path, 'config.json'),
        '-n', os.path.basename(model_path),
        '-i', args.input,
        '-o', args.output
    ]
    print('実行コマンド:', ' '.join(cmd))
    subprocess.run(cmd)

if __name__ == '__main__':
    main()
