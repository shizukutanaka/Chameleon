import argparse
import sounddevice as sd
import soundfile as sf

def record_audio(output_file: str, duration: int = 5, samplerate: int = 44100, channels: int = 1):
    print(f"マイクから{duration}秒間録音します...")
    audio = sd.rec(int(duration * samplerate), samplerate=samplerate, channels=channels, dtype='int16')
    sd.wait()
    sf.write(output_file, audio, samplerate)
    print(f"録音完了: {output_file}")

def main():
    parser = argparse.ArgumentParser(description='マイク音声を録音してwavファイルに保存')
    parser.add_argument('--output', required=True, help='保存先wavファイル名')
    parser.add_argument('--duration', type=int, default=5, help='録音時間（秒）')
    parser.add_argument('--samplerate', type=int, default=44100, help='サンプリングレート')
    parser.add_argument('--channels', type=int, default=1, help='チャンネル数（通常1=モノラル, 2=ステレオ）')
    args = parser.parse_args()

    record_audio(args.output, args.duration, args.samplerate, args.channels)

if __name__ == '__main__':
    main()
