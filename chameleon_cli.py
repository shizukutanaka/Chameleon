#!/usr/bin/env python3
"""
Chameleon Audio CLI - Unified command-line interface
"""

import argparse
import os
import sys
from pathlib import Path

# Import all modules
from chameleon import AudioProcessor
from audio_mixer import SimpleAudioMixer, AutoMixer
from audio_visualizer import AudioReport, TextVisualizer
from audio_recorder import SimpleRecorder, AudioCapture
from batch_processor import SmartBatchProcessor, BatchOperations
from realtime_processor import StreamProcessor, RealtimeEffects


def cmd_info(args):
    """Show audio file information"""
    processor = AudioProcessor()

    if not os.path.exists(args.input):
        print(f"File not found: {args.input}")
        return 1

    info = processor._get_file_info(args.input)
    if not info:
        print(f"Could not analyze file: {args.input}")
        return 1

    print(f"File: {args.input}")
    print(f"Format: {info.get('format', 'unknown')}")
    print(f"Duration: {info.get('duration', 0):.2f} seconds")
    print(f"Sample Rate: {info.get('sample_rate', 0)} Hz")
    print(f"Channels: {info.get('channels', 0)}")
    print(f"Size: {info.get('size_bytes', 0)} bytes")

    # Show metadata if available
    metadata = info.get('metadata', {})
    if metadata:
        print("\nMetadata:")
        for key, value in metadata.items():
            print(f"  {key.title()}: {value}")

    return 0


def cmd_convert(args):
    """Convert audio files"""
    processor = AudioProcessor()

    if not os.path.exists(args.input):
        print(f"Input file not found: {args.input}")
        return 1

    # Load input
    samples, info = processor.load_wav(args.input)
    if not samples:
        print(f"Could not load audio: {args.input}")
        return 1

    # Process based on options
    processed = samples

    if args.normalize:
        processed = processor.normalize(processed, args.peak or 0.95)
        print("Applied normalization")

    if args.denoise:
        processed = processor.reduce_noise(processed, args.noise_floor or -40)
        print("Applied noise reduction")

    if args.compress:
        processed = processor.apply_compressor(processed, args.threshold or -20, args.ratio or 0.3)
        print("Applied compression")

    # Save output
    output_path = args.output or f"{Path(args.input).stem}_processed.wav"
    success = processor.save_wav(output_path, processed, info['sample_rate'])

    if success:
        print(f"Saved to: {output_path}")
        return 0
    else:
        print("Failed to save output")
        return 1


def cmd_mix(args):
    """Mix audio files"""
    mixer = SimpleAudioMixer()

    # Parse input files and parameters
    inputs = args.input.split(',')
    volumes = [float(v) for v in (args.volumes.split(',') if args.volumes else ['1.0'] * len(inputs))]
    start_times = [float(t) for t in (args.times.split(',') if args.times else ['0.0'] * len(inputs))]

    # Pad lists to match input count
    while len(volumes) < len(inputs):
        volumes.append(1.0)
    while len(start_times) < len(inputs):
        start_times.append(0.0)

    # Add tracks
    for i, input_file in enumerate(inputs):
        input_file = input_file.strip()
        if os.path.exists(input_file):
            mixer.add_track(input_file, volumes[i], start_times[i],
                          args.fade_in or 0.0, args.fade_out or 0.0)
        else:
            print(f"Warning: File not found: {input_file}")

    # Export mix
    output_path = args.output or "mixed_output.wav"
    success = mixer.export_mix(output_path, args.duration, normalize=True)

    if success:
        print(f"Mix saved to: {output_path}")
        return 0
    else:
        print("Mix failed")
        return 1


def cmd_visualize(args):
    """Generate audio visualization"""
    if args.report:
        # Generate full report
        reporter = AudioReport()
        output_path = args.output or f"{Path(args.input).stem}_report.txt"
        success = reporter.save_report(args.input, output_path)

        if success:
            print(f"Report saved to: {output_path}")
            return 0
        else:
            print("Report generation failed")
            return 1
    else:
        # Show quick visualization
        processor = AudioProcessor()
        samples, _ = processor.load_wav(args.input)

        if not samples:
            print(f"Could not load audio: {args.input}")
            return 1

        visualizer = TextVisualizer(width=args.width or 80, height=args.height or 20)

        if args.type == 'waveform':
            lines = visualizer.draw_waveform(samples[:44100], f"Waveform: {args.input}")
        elif args.type == 'spectrum':
            lines = visualizer.draw_spectrum(samples[:44100], f"Spectrum: {args.input}")
        elif args.type == 'levels':
            lines = visualizer.draw_levels(samples[:44100], f"Levels: {args.input}")
        else:
            print(f"Unknown visualization type: {args.type}")
            return 1

        for line in lines:
            print(line)

        return 0


def cmd_record(args):
    """Record audio"""
    recorder = SimpleRecorder(args.sample_rate or 44100, args.channels or 1)

    if args.test_tone:
        # Generate test tone instead
        output_path = args.output or "test_tone.wav"
        test_file = recorder.generate_test_tone(args.frequency or 440,
                                              args.duration or 5.0, output_path)
        print(f"Generated test tone: {test_file}")
        return 0
    else:
        # Try actual recording
        output_path = args.output or "recording.wav"
        result = recorder.record_audio(args.duration or 5, output_path)

        if result:
            print(f"Recording saved: {result}")
            return 0
        else:
            print("Recording failed")
            return 1


def cmd_batch(args):
    """Batch process files"""
    if not os.path.exists(args.input):
        print(f"Directory not found: {args.input}")
        return 1

    operation = args.operation
    output_dir = args.output

    if operation == 'normalize':
        success = BatchOperations.normalize_directory(args.input, output_dir, args.recursive)
    elif operation == 'denoise':
        success = BatchOperations.denoise_directory(args.input, output_dir, args.noise_floor or -40)
    elif operation == 'analyze':
        success = BatchOperations.analyze_directory(args.input, output_dir)
    else:
        print(f"Unknown batch operation: {operation}")
        return 1

    return 0 if success else 1


def cmd_realtime(args):
    """Real-time processing demo"""
    # Create processor with preset
    processor = StreamProcessor()

    if args.preset == 'voice':
        processor.pipeline = RealtimeEffects.create_voice_enhancer()
    elif args.preset == 'music':
        processor.pipeline = RealtimeEffects.create_music_enhancer()
    elif args.preset == 'podcast':
        processor.pipeline = RealtimeEffects.create_podcast_processor()
    else:
        print(f"Unknown preset: {args.preset}")
        return 1

    print(f"Real-time processing demo with {args.preset} preset")
    print("Processing test signal...")

    # Demo with test signal
    import array
    import math
    import time

    processor.start()

    # Generate and process test chunks
    for i in range(10):
        chunk = array.array('h')
        for j in range(1024):
            t = (i * 1024 + j) / 44100
            sample = int(5000 * math.sin(2 * math.pi * 440 * t))
            chunk.append(sample)

        processor.feed(chunk)
        output = processor.get_output(timeout=0.1)

        if output:
            print(f"Processed chunk {i+1}: {len(output)} samples")

        time.sleep(0.01)

    # Show stats
    stats = processor.get_stats()
    print(f"\nProcessing stats:")
    print(f"  Chunks processed: {stats['chunks_processed']}")
    print(f"  Realtime factor: {stats.get('realtime_factor', 0):.2f}x")

    processor.stop()
    return 0


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Chameleon Audio System - Unified CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s info audio.wav                    # Show file information
  %(prog)s convert audio.wav --normalize     # Normalize audio
  %(prog)s mix "a.wav,b.wav" --output mix.wav # Mix files
  %(prog)s visualize audio.wav --type levels # Show level meters
  %(prog)s record --duration 10 --output rec.wav # Record 10 seconds
  %(prog)s batch /audio/dir --operation normalize # Batch normalize
  %(prog)s realtime --preset voice          # Real-time voice processing
        """)

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Info command
    info_parser = subparsers.add_parser('info', help='Show audio file information')
    info_parser.add_argument('input', help='Input audio file')

    # Convert command
    convert_parser = subparsers.add_parser('convert', help='Convert and process audio')
    convert_parser.add_argument('input', help='Input audio file')
    convert_parser.add_argument('-o', '--output', help='Output file path')
    convert_parser.add_argument('--normalize', action='store_true', help='Normalize audio')
    convert_parser.add_argument('--denoise', action='store_true', help='Apply noise reduction')
    convert_parser.add_argument('--compress', action='store_true', help='Apply compression')
    convert_parser.add_argument('--peak', type=float, help='Normalization peak (0.0-1.0)')
    convert_parser.add_argument('--noise-floor', type=float, help='Noise floor in dB')
    convert_parser.add_argument('--threshold', type=float, help='Compression threshold in dB')
    convert_parser.add_argument('--ratio', type=float, help='Compression ratio')

    # Mix command
    mix_parser = subparsers.add_parser('mix', help='Mix multiple audio files')
    mix_parser.add_argument('input', help='Comma-separated list of input files')
    mix_parser.add_argument('-o', '--output', help='Output mix file')
    mix_parser.add_argument('--volumes', help='Comma-separated volumes (e.g., 1.0,0.8,0.5)')
    mix_parser.add_argument('--times', help='Comma-separated start times (e.g., 0,2.5,5.0)')
    mix_parser.add_argument('--duration', type=float, help='Mix duration in seconds')
    mix_parser.add_argument('--fade-in', type=float, help='Fade-in time in seconds')
    mix_parser.add_argument('--fade-out', type=float, help='Fade-out time in seconds')

    # Visualize command
    viz_parser = subparsers.add_parser('visualize', help='Visualize audio')
    viz_parser.add_argument('input', help='Input audio file')
    viz_parser.add_argument('--type', choices=['waveform', 'spectrum', 'levels'],
                           default='waveform', help='Visualization type')
    viz_parser.add_argument('--width', type=int, default=80, help='Display width')
    viz_parser.add_argument('--height', type=int, default=20, help='Display height')
    viz_parser.add_argument('--report', action='store_true', help='Generate full report')
    viz_parser.add_argument('-o', '--output', help='Output report file')

    # Record command
    record_parser = subparsers.add_parser('record', help='Record audio')
    record_parser.add_argument('-o', '--output', help='Output recording file')
    record_parser.add_argument('--duration', type=float, default=5.0, help='Recording duration')
    record_parser.add_argument('--sample-rate', type=int, help='Sample rate')
    record_parser.add_argument('--channels', type=int, help='Number of channels')
    record_parser.add_argument('--test-tone', action='store_true', help='Generate test tone instead')
    record_parser.add_argument('--frequency', type=float, help='Test tone frequency')

    # Batch command
    batch_parser = subparsers.add_parser('batch', help='Batch process files')
    batch_parser.add_argument('input', help='Input directory')
    batch_parser.add_argument('--operation', choices=['normalize', 'denoise', 'analyze'],
                             required=True, help='Batch operation')
    batch_parser.add_argument('-o', '--output', help='Output directory')
    batch_parser.add_argument('--recursive', action='store_true', help='Process recursively')
    batch_parser.add_argument('--noise-floor', type=float, help='Noise floor for denoising')

    # Realtime command
    rt_parser = subparsers.add_parser('realtime', help='Real-time processing demo')
    rt_parser.add_argument('--preset', choices=['voice', 'music', 'podcast'],
                          default='voice', help='Processing preset')

    # Parse arguments
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Route to appropriate command
    commands = {
        'info': cmd_info,
        'convert': cmd_convert,
        'mix': cmd_mix,
        'visualize': cmd_visualize,
        'record': cmd_record,
        'batch': cmd_batch,
        'realtime': cmd_realtime
    }

    if args.command in commands:
        try:
            return commands[args.command](args)
        except KeyboardInterrupt:
            print("\nOperation cancelled")
            return 1
        except Exception as e:
            print(f"Error: {e}")
            return 1
    else:
        print(f"Unknown command: {args.command}")
        return 1


if __name__ == '__main__':
    sys.exit(main())