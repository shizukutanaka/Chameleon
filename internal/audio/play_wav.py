import argparse
import sounddevice as sd
import soundfile as sf

def play_audio(input_file):
    data, samplerate = sf.read(input_file, dtype='float32')
    sd.play(data, samplerate)
    sd.wait()

def main():
    parser = argparse.ArgumentParser(description='wavファイルを再生')
    parser.add_argument('--input', required=True, help='再生するwavファイル')
    args = parser.parse_args()
    play_audio(args.input)

if __name__ == '__main__':
    main()
