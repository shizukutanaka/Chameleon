import argparse
import os
import subprocess
import sounddevice as sd
import soundfile as sf
import sys

def record_audio(output_file: str, duration: int = 5, samplerate: int = 44100, channels: int = 1):
    print(f"マイクから{duration}秒間録音します...")
    audio = sd.rec(int(duration * samplerate), samplerate=samplerate, channels=channels, dtype='int16')
    sd.wait()
    sf.write(output_file, audio, samplerate)
    print(f"録音完了: {output_file}")

def play_audio(audio_file: str):
    print(f"再生中: {audio_file}")
    data, samplerate = sf.read(audio_file, dtype='float32')
    sd.play(data, samplerate)
    sd.wait()
    print("再生終了")

def main():
    parser = argparse.ArgumentParser(description='マイク録音→ボイス変換→自動再生ワンストップ')
    parser.add_argument('--target_voice', required=True, help='変換先の声モデル名')
    parser.add_argument('--duration', type=int, default=5, help='録音時間（秒）')
    parser.add_argument('--samplerate', type=int, default=44100, help='サンプリングレート')
    parser.add_argument('--channels', type=int, default=1, help='チャンネル数')
    parser.add_argument('--tmp_dir', default='tmp', help='一時ファイル保存先')
    parser.add_argument('--svc_root', default='so-vits-svc', help='so-vits-svc等のルートパス')
    args = parser.parse_args()

    os.makedirs(args.tmp_dir, exist_ok=True)
    input_wav = os.path.join(args.tmp_dir, 'mic_input.wav')
    output_wav = os.path.join(args.tmp_dir, 'mic_changed.wav')

    try:
        record_audio(input_wav, args.duration, args.samplerate, args.channels)
    except Exception as e:
        print(f"録音失敗: {e}")
        sys.exit(1)

    # ボイス変換
    try:
        cmd = [
            sys.executable, os.path.join(os.path.dirname(__file__), 'voice_changer.py'),
            '--input', input_wav,
            '--target_voice', args.target_voice,
            '--output', output_wav,
            '--svc_root', args.svc_root
        ]
        print('ボイス変換コマンド:', ' '.join(cmd))
        subprocess.run(cmd, check=True)
    except Exception as e:
        print(f"変換失敗: {e}")
        sys.exit(1)

    # 再生
    try:
        play_audio(output_wav)
    except Exception as e:
        print(f"再生失敗: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
