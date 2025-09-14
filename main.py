#!/usr/bin/env python3
"""
Chameleon Audio System - Unified Entry Point
Fast, practical audio processing tool
"""

import sys
import os
import argparse
import time
import struct
import wave
import array
import json
from pathlib import Path
from typing import Optional, List

# Core imports
import audio_utils
import audio_processor
import voice_processor
import config_manager
import file_optimizer
import plugins
import audio_detector
import quality_monitor
from audio_formats import AudioFormatHandler
from input_validator import validate_file_path, validate_audio_params, validate_preset_name, ValidationError

# Phase 5 imports - Cutting-edge features
from audio_synthesis import AudioSynthesizer, WaveformType, demo_synthesis
from spatial_audio import SpatialAudioProcessor, SpatialMode, Position3D, demo_spatial_audio
from ml_audio import MLAudioProcessor, AudioClassification, EmotionType, demo_ml_audio

# Phase 6 imports - Enterprise/Production features
from network_audio import LiveAudioProcessor, AudioStreamer, AudioReceiver, StreamingQuality, StreamingProtocol, demo_network_audio
from advanced_codecs import AdvancedAudioCodecManager, CodecType, CompressionType, demo_advanced_codecs
from ml_training import AudioDataset, NeuralNetworkTrainer, ModelManager, ModelType, demo_ml_training

def main():
    parser = argparse.ArgumentParser(description='Chameleon Audio Processor')
    
    # Global options
    parser.add_argument('--config', help='Configuration file path')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--sample-rate', type=int, help='Override sample rate')
    parser.add_argument('--buffer-size', type=int, help='Override buffer size')
    
    # Subcommands
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Voice transformation command
    voice_parser = subparsers.add_parser('voice', help='Voice transformation')
    voice_parser.add_argument('input', help='Input audio file')
    voice_parser.add_argument('output', help='Output audio file')
    voice_parser.add_argument('--preset', choices=['normal', 'male', 'female', 'child', 'robot', 'deep', 'cartoon'],
                             default='normal', help='Voice preset')
    voice_parser.add_argument('--pitch', type=float, help='Pitch factor (0.5-2.0)')
    voice_parser.add_argument('--formant', type=float, help='Formant factor (0.5-2.0)')
    voice_parser.add_argument('--speed', type=float, help='Speed factor (0.5-2.0)')
    
    # Audio effects command
    effects_parser = subparsers.add_parser('effect', help='Apply audio effects')
    effects_parser.add_argument('input', help='Input audio file')
    effects_parser.add_argument('output', help='Output audio file')
    effects_parser.add_argument('--reverb', type=float, help='Reverb amount (0-1)')
    effects_parser.add_argument('--delay', type=float, help='Delay time in seconds')
    effects_parser.add_argument('--chorus', type=float, help='Chorus amount (0-1)')
    effects_parser.add_argument('--distortion', type=float, help='Distortion amount (0-1)')
    
    # Real-time processing
    realtime_parser = subparsers.add_parser('realtime', help='Real-time voice processing')
    realtime_parser.add_argument('--preset', choices=['normal', 'male', 'female', 'child', 'robot', 'deep', 'cartoon'],
                                default='normal', help='Voice preset')
    realtime_parser.add_argument('--duration', type=float, help='Duration in seconds (default: continuous)')
    
    # Analyze command
    analyze_parser = subparsers.add_parser('analyze', help='Analyze audio file')
    analyze_parser.add_argument('input', help='Input audio file')
    
    # Batch processing
    batch_parser = subparsers.add_parser('batch', help='Batch process multiple files')
    batch_parser.add_argument('input_dir', help='Input directory')
    batch_parser.add_argument('output_dir', help='Output directory')
    batch_parser.add_argument('--preset', help='Voice preset to apply')
    batch_parser.add_argument('--format', help='Output format')
    
    # Optimization command
    optimize_parser = subparsers.add_parser('optimize', help='Optimize audio files')
    optimize_parser.add_argument('input', help='Input audio file or directory')
    optimize_parser.add_argument('output', help='Output audio file or directory')
    optimize_parser.add_argument('--level', choices=['low', 'medium', 'high', 'maximum'],
                                 default='medium', help='Optimization level')
    
    # Plugin command
    plugin_parser = subparsers.add_parser('plugin', help='Manage and apply audio plugins')
    plugin_subparsers = plugin_parser.add_subparsers(dest='plugin_action', help='Plugin actions')
    
    # Plugin list
    plugin_list_parser = plugin_subparsers.add_parser('list', help='List available plugins')
    plugin_list_parser.add_argument('--type', help='Filter by plugin type')
    plugin_list_parser.add_argument('--category', help='Filter by category')
    
    # Plugin apply
    plugin_apply_parser = plugin_subparsers.add_parser('apply', help='Apply plugins to audio')
    plugin_apply_parser.add_argument('input', help='Input audio file')
    plugin_apply_parser.add_argument('output', help='Output audio file')
    plugin_apply_parser.add_argument('--plugins', nargs='+', help='Plugins to apply in order')
    plugin_apply_parser.add_argument('--chain', help='Named plugin chain to apply')
    
    # Plugin create
    plugin_create_parser = plugin_subparsers.add_parser('create', help='Create new plugin project')
    plugin_create_parser.add_argument('name', help='Plugin name')
    plugin_create_parser.add_argument('--type', choices=['effect', 'generator', 'analyzer'], 
                                     default='effect', help='Plugin type')
    plugin_create_parser.add_argument('--output-dir', help='Output directory')
    
    # Plugin demo
    plugin_demo_parser = plugin_subparsers.add_parser('demo', help='Run plugin system demo')
    
    # Plugin load
    plugin_load_parser = plugin_subparsers.add_parser('load', help='Load plugin from file')
    plugin_load_parser.add_argument('file', help='Plugin file path')
    
    # Plugin generate
    plugin_gen_parser = plugin_subparsers.add_parser('generate', help='Generate audio using generator plugins')
    plugin_gen_parser.add_argument('output', help='Output audio file')
    plugin_gen_parser.add_argument('--generator', required=True, help='Generator plugin name')
    plugin_gen_parser.add_argument('--duration', type=float, default=5.0, help='Duration in seconds')
    plugin_gen_parser.add_argument('--params', help='JSON parameters for generator')
    plugin_parser.add_argument('--reverb-room', type=float, default=0.5, help='Reverb room size')
    plugin_parser.add_argument('--reverb-wet', type=float, default=0.3, help='Reverb wet level')
    plugin_parser.add_argument('--distortion-drive', type=float, default=1.5, help='Distortion drive')
    plugin_parser.add_argument('--chorus-depth', type=float, default=0.5, help='Chorus depth')
    
    # Quality command
    quality_parser = subparsers.add_parser('quality', help='Audio quality analysis and correction')
    quality_parser.add_argument('input', help='Input audio file')
    quality_parser.add_argument('output', nargs='?', help='Output audio file (for correction)')
    quality_parser.add_argument('--analyze-only', action='store_true', help='Only analyze, do not correct')
    quality_parser.add_argument('--target-quality', type=float, default=80.0, help='Target quality score')
    
    # Convert command (format conversion)
    convert_parser = subparsers.add_parser('convert', help='Convert audio format')
    convert_parser.add_argument('input', help='Input audio file')
    convert_parser.add_argument('output', help='Output audio file')
    convert_parser.add_argument('--sample-rate-out', type=int, help='Output sample rate')
    convert_parser.add_argument('--quality', choices=['low', 'medium', 'high'], default='medium', help='Conversion quality')
    
    # Detect command (format detection and analysis)
    detect_parser = subparsers.add_parser('detect', help='Detect and analyze audio file format')
    detect_parser.add_argument('input', help='Input audio file')
    detect_parser.add_argument('--detailed', action='store_true', help='Show detailed format analysis')
    
    # List presets command
    list_parser = subparsers.add_parser('list-presets', help='List available voice presets')
    list_parser.add_argument('--detailed', action='store_true', help='Show detailed preset information')
    
    # Spectrum analysis command
    spectrum_parser = subparsers.add_parser('spectrum', help='Analyze audio spectrum')
    spectrum_parser.add_argument('input', help='Input audio file')
    spectrum_parser.add_argument('--detailed', action='store_true', help='Show detailed spectrum analysis')
    
    # Record command
    record_parser = subparsers.add_parser('record', help='Record audio from microphone')
    record_parser.add_argument('output', nargs='?', help='Output filename')
    record_parser.add_argument('--duration', type=float, help='Recording duration in seconds')
    record_parser.add_argument('--auto-stop', action='store_true', help='Auto-stop on silence')
    
    # Denoise command
    denoise_parser = subparsers.add_parser('denoise', help='Remove noise and enhance audio')
    denoise_parser.add_argument('input', help='Input audio file')
    denoise_parser.add_argument('output', help='Output audio file')
    denoise_parser.add_argument('--noise-reduction', type=float, default=0.5, help='Noise reduction (0.0-1.0)')
    denoise_parser.add_argument('--clarity', type=float, default=1.2, help='Clarity enhancement (1.0-2.0)')
    denoise_parser.add_argument('--compress', action='store_true', help='Apply compression')
    
    # Interactive mode command
    interactive_parser = subparsers.add_parser('interactive', help='Interactive parameter adjustment mode')
    interactive_parser.add_argument('input', nargs='?', help='Optional input audio file')
    
    # Visualize command
    visualize_parser = subparsers.add_parser('visualize', help='Audio visualization')
    visualize_parser.add_argument('input', help='Input audio file')
    visualize_parser.add_argument('--style', choices=['waveform', 'spectrum', 'spectrogram', 'level', 'combined'],
                                 default='combined', help='Visualization style')
    visualize_parser.add_argument('--duration', type=float, help='Visualization duration')
    
    # Mix command
    mix_parser = subparsers.add_parser('mix', help='Multi-track audio mixing')
    mix_parser.add_argument('output', help='Output mixed audio file')
    mix_parser.add_argument('tracks', nargs='+', help='Input track files')
    mix_parser.add_argument('--volumes', nargs='*', type=float, help='Track volumes (0.0-2.0)')
    mix_parser.add_argument('--pans', nargs='*', type=float, help='Track pans (-1.0 to 1.0)')
    mix_parser.add_argument('--master-volume', type=float, default=1.0, help='Master volume')
    
    # Script command  
    script_parser = subparsers.add_parser('script', help='Execute audio processing scripts')
    script_parser.add_argument('action', choices=['create', 'execute', 'templates'], help='Script action')
    script_parser.add_argument('--template', help='Template name for create action')
    script_parser.add_argument('--input', help='Input file for create action')
    script_parser.add_argument('--output', help='Output file for create action')
    script_parser.add_argument('--script-file', help='Script file for execute action')
    
    # Pipeline command
    pipeline_parser = subparsers.add_parser('pipeline', help='Advanced format conversion')
    pipeline_parser.add_argument('action', choices=['convert', 'batch', 'profiles'], help='Pipeline action')
    pipeline_parser.add_argument('--input', help='Input file or directory')
    pipeline_parser.add_argument('--output', help='Output file or directory')
    pipeline_parser.add_argument('--profile', default='cd_quality_wav', help='Conversion profile')
    
    # Restore command
    restore_parser = subparsers.add_parser('restore', help='Audio restoration and repair')
    restore_parser.add_argument('action', choices=['repair', 'analyze', 'profiles'], help='Restoration action')
    restore_parser.add_argument('--input', help='Input audio file')
    restore_parser.add_argument('--output', help='Output audio file')
    restore_parser.add_argument('--profile', default='digital_repair', help='Restoration profile')
    
    # Synthesis command [Phase 5]
    synth_parser = subparsers.add_parser('synthesize', help='Audio synthesis and generation')
    synth_parser.add_argument('action', choices=['tone', 'chord', 'arpeggio', 'drums', 'sequence', 'demo'], help='Synthesis action')
    synth_parser.add_argument('--output', help='Output audio file')
    synth_parser.add_argument('--frequency', type=float, default=440.0, help='Base frequency (Hz)')
    synth_parser.add_argument('--duration', type=float, default=2.0, help='Duration (seconds)')
    synth_parser.add_argument('--waveform', choices=['sine', 'sawtooth', 'square', 'triangle', 'noise'], 
                             default='sine', help='Waveform type')
    synth_parser.add_argument('--amplitude', type=float, default=0.5, help='Amplitude (0.0-1.0)')
    synth_parser.add_argument('--bpm', type=int, default=120, help='BPM for drum patterns')
    synth_parser.add_argument('--synth-type', choices=['subtractive', 'fm'], default='subtractive', help='Synthesizer type')
    synth_parser.add_argument('--frequencies', nargs='+', type=float, help='Multiple frequencies for chords/arpeggios')
    synth_parser.add_argument('--sequence-file', help='JSON file with sequence data')
    
    # Spatial audio command [Phase 5]
    spatial_parser = subparsers.add_parser('spatial', help='Spatial audio and 3D processing')
    spatial_parser.add_argument('action', choices=['position', 'surround', 'room', 'demo'], help='Spatial processing action')
    spatial_parser.add_argument('--input', help='Input audio file')
    spatial_parser.add_argument('--output', help='Output audio file')
    spatial_parser.add_argument('--mode', choices=['stereo', 'binaural', 'surround_5_1', 'surround_7_1'], 
                               default='binaural', help='Spatial mode')
    spatial_parser.add_argument('--position', nargs=3, type=float, default=[0.0, 0.0, 0.0], 
                               help='3D position (x y z)')
    spatial_parser.add_argument('--listener', nargs=3, type=float, default=[0.0, 0.0, 0.0], 
                               help='Listener position (x y z)')
    spatial_parser.add_argument('--room-size', type=float, default=10.0, help='Room size (meters)')
    spatial_parser.add_argument('--damping', type=float, default=0.3, help='Room damping (0.0-1.0)')
    spatial_parser.add_argument('--sources-file', help='JSON file with multiple positioned sources')
    
    # Machine Learning command [Phase 5]
    ml_parser = subparsers.add_parser('ml', help='Machine learning audio analysis')
    ml_parser.add_argument('action', choices=['analyze', 'classify', 'emotion', 'segment', 'anomaly', 'demo'], 
                          help='ML analysis action')
    ml_parser.add_argument('--input', help='Input audio file')
    ml_parser.add_argument('--output', help='Output analysis file (JSON)')
    ml_parser.add_argument('--detailed', action='store_true', help='Detailed analysis output')
    ml_parser.add_argument('--threshold', type=float, default=0.01, help='Energy threshold for segmentation')
    ml_parser.add_argument('--export-features', help='Export features to CSV file')
    
    # Network streaming command [Phase 6]
    network_parser = subparsers.add_parser('stream', help='Real-time audio streaming and networking')
    network_parser.add_argument('action', choices=['server', 'client', 'broadcast', 'receive', 'demo'], 
                               help='Network streaming action')
    network_parser.add_argument('--host', default='localhost', help='Server host address')
    network_parser.add_argument('--port', type=int, default=8888, help='Server port')
    network_parser.add_argument('--protocol', choices=['udp_raw', 'tcp_reliable'], default='udp_raw',
                               help='Streaming protocol')
    network_parser.add_argument('--quality', choices=['low', 'medium', 'high', 'broadcast'], 
                               default='medium', help='Streaming quality')
    network_parser.add_argument('--input', help='Audio file to stream')
    network_parser.add_argument('--output', help='Output file for received audio')
    network_parser.add_argument('--duration', type=float, default=10.0, help='Streaming duration (seconds)')
    network_parser.add_argument('--monitor', action='store_true', help='Show quality monitoring')
    
    # Advanced codecs command [Phase 6]
    codec_parser = subparsers.add_parser('codec', help='Advanced audio codecs and compression')
    codec_parser.add_argument('action', choices=['encode', 'decode', 'compare', 'demo'], help='Codec action')
    codec_parser.add_argument('--input', help='Input audio file')
    codec_parser.add_argument('--output', help='Output file')
    codec_parser.add_argument('--codec', choices=['adpcm', 'psychoacoustic', 'wavelet'], 
                             default='psychoacoustic', help='Codec type')
    codec_parser.add_argument('--quality', type=float, default=0.8, help='Compression quality (0.0-1.0)')
    codec_parser.add_argument('--encoded-file', help='Encoded data file (JSON)')
    codec_parser.add_argument('--compare-all', action='store_true', help='Compare all available codecs')
    
    # ML Training command [Phase 6]
    train_parser = subparsers.add_parser('train', help='Machine learning training and model management')
    train_parser.add_argument('action', choices=['dataset', 'train', 'evaluate', 'models', 'demo'], 
                             help='Training action')
    train_parser.add_argument('--dataset-dir', help='Audio dataset directory')
    train_parser.add_argument('--model-name', help='Model name')
    train_parser.add_argument('--model-type', choices=['audio_classifier', 'emotion_detector'], 
                             default='audio_classifier', help='Model type')
    train_parser.add_argument('--epochs', type=int, default=100, help='Training epochs')
    train_parser.add_argument('--learning-rate', type=float, default=0.01, help='Learning rate')
    train_parser.add_argument('--output-dir', default='models', help='Model output directory')
    train_parser.add_argument('--augment', action='store_true', help='Apply data augmentation')
    train_parser.add_argument('--version', help='Model version to load')
    
    args = parser.parse_args()
    
    # Initialize configuration
    config = config_manager.get_config()
    if args.config:
        config.config_file = args.config
        config.load()
    
    # Override config with command line arguments
    if args.verbose:
        config.set('ui', 'verbose', True)
    if args.sample_rate:
        config.set('audio', 'sample_rate', args.sample_rate)
    if args.buffer_size:
        config.set('audio', 'buffer_size', args.buffer_size)
    
    if not args.command:
        parser.print_help()
        return 1
    
    try:
        if args.command == 'voice':
            process_voice(args)
        elif args.command == 'effect':
            process_effects(args)
        elif args.command == 'realtime':
            process_realtime(args)
        elif args.command == 'analyze':
            analyze_audio(args)
        elif args.command == 'batch':
            process_batch(args)
        elif args.command == 'optimize':
            process_optimize(args)
        elif args.command == 'plugin':
            process_plugins(args)
        elif args.command == 'quality':
            process_quality(args)
        elif args.command == 'convert':
            process_convert(args)
        elif args.command == 'detect':
            process_detect(args)
        elif args.command == 'list-presets':
            list_presets(args)
        elif args.command == 'spectrum':
            process_spectrum(args)
        elif args.command == 'record':
            process_record(args)
        elif args.command == 'denoise':
            process_denoise(args)
        elif args.command == 'interactive':
            process_interactive(args)
        elif args.command == 'visualize':
            process_visualize(args)
        elif args.command == 'mix':
            process_mix(args)
        elif args.command == 'script':
            process_script(args)
        elif args.command == 'pipeline':
            process_pipeline(args)
        elif args.command == 'restore':
            process_restore(args)
        elif args.command == 'synthesize':
            process_synthesize(args)
        elif args.command == 'spatial':
            process_spatial(args)
        elif args.command == 'ml':
            process_ml(args)
        elif args.command == 'stream':
            process_stream(args)
        elif args.command == 'codec':
            process_codec(args)
        elif args.command == 'train':
            process_train(args)
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

def process_voice(args):
    """Process voice transformation"""
    try:
        # 入力検証
        input_path = validate_file_path(args.input, 'read')
        output_path = validate_file_path(args.output, 'write')
        preset = validate_preset_name(args.preset) if args.preset else 'normal'
        
        print(f"Processing {input_path} -> {output_path}")
        
        # Load audio
        handler = AudioFormatHandler()
        audio_data, metadata = handler.load_audio(input_path)
        sample_rate = metadata.get('sample_rate', 44100)
        
        # Create voice processor
        processor = voice_processor.VoiceProcessor(sample_rate)
        
        # Load preset or custom parameters
        processor.load_preset(preset)
        
        # Override with custom parameters if provided (with validation)
        custom_params = {}
        if args.pitch:
            custom_params['pitch'] = args.pitch
        if args.formant:
            custom_params['formant'] = args.formant
        if args.speed:
            custom_params['speed'] = args.speed
            
        if custom_params:
            validated_params = validate_audio_params(custom_params)
            if 'pitch' in validated_params:
                processor.profile.pitch = validated_params['pitch']
            if 'formant' in validated_params:
                processor.profile.formant = validated_params['formant']
            if 'speed' in validated_params:
                processor.profile.speed = validated_params['speed']
        
        # Process audio
        processed = processor.process_chunk(audio_data)
        
        # Save output
        handler.save_audio(processed, output_path, 
                          sample_rate=metadata.get('sample_rate', 44100),
                          channels=metadata.get('channels', 1))
        print(f"Saved to {output_path}")
        
    except ValidationError as e:
        print(f"Validation error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Processing error: {e}", file=sys.stderr)
        return 1

def process_effects(args):
    """Apply audio effects"""
    print(f"Applying effects to {args.input}")
    
    # Load audio
    handler = AudioFormatHandler()
    audio_data, metadata = handler.load_audio(args.input)
    sample_rate = metadata.get('sample_rate', 44100)
    
    # Create audio processor
    processor = audio_processor.AudioProcessor(sample_rate)
    
    # Build parameters
    params = {}
    if args.reverb:
        params['reverb'] = args.reverb
    if args.delay:
        params['delay'] = args.delay
    if args.chorus:
        params['filter'] = 'bandpass'  # Simple chorus simulation
        params['gain'] = 1.0 + args.chorus * 0.2
    if args.distortion:
        params['gain'] = 1.0 + args.distortion * 2.0
    
    # Process audio
    processed = processor.process_audio(audio_data, params)
    
    # Save output
    handler.save_audio(processed, args.output, 
                      sample_rate=metadata.get('sample_rate', 44100),
                      channels=metadata.get('channels', 1))
    print(f"Saved to {args.output}")

def process_realtime(args):
    """Process voice in real-time"""
    print(f"Starting real-time voice processing with preset: {args.preset}")
    print("Press Ctrl+C to stop")
    
    try:
        # Create processor
        processor = voice_processor.VoiceProcessor()
        processor.load_preset(args.preset)
        
        # Create stream processor for real-time processing
        import stream_processor
        stream_proc = stream_processor.StreamProcessor()
        
        # Configure with voice preset
        stream_proc.set_voice_preset(args.preset)
        
        # Start streaming
        if hasattr(stream_proc, 'start_streaming'):
            try:
                stream_proc.start_streaming(duration=args.duration)
                print("Real-time processing completed successfully")
            except Exception as e:
                print(f"Real-time processing error: {e}")
        else:
            print("Real-time streaming not yet fully implemented")
        
    except KeyboardInterrupt:
        print("\nStopping real-time processing")
    finally:
        if 'audio_in' in locals():
            audio_in.close()
        if 'audio_out' in locals():
            audio_out.close()

def analyze_audio(args):
    """Analyze audio file"""
    print(f"Analyzing {args.input}")
    
    # Load audio
    handler = AudioFormatHandler()
    audio_data, metadata = handler.load_audio(args.input)
    sample_rate = metadata.get('sample_rate', 44100)
    
    # Create processor for analysis
    processor = voice_processor.VoiceProcessor(sample_rate)
    
    # Analyze
    metrics = processor.analyze_voice(audio_data)
    
    # Display results
    print("\nAudio Analysis:")
    print(f"  Sample Rate: {sample_rate} Hz")
    print(f"  Duration: {len(audio_data) / (sample_rate * 2):.2f} seconds")
    print(f"  Channels: {metadata.get('channels', 1)}")
    
    if metrics:
        print("\nVoice Characteristics:")
        print(f"  Pitch: {metrics.get('pitch_hz', 0):.1f} Hz")
        print(f"  Formant F1: {metrics.get('formant_f1', 0):.1f} Hz")
        print(f"  Formant F2: {metrics.get('formant_f2', 0):.1f} Hz")
        print(f"  Energy: {metrics.get('energy', 0):.1f}")
        print(f"  Zero Crossings: {metrics.get('zero_crossings', 0)}")

def process_batch(args):
    """Batch process audio files"""
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    
    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Find audio files
    audio_extensions = ['.wav', '.mp3', '.flac', '.ogg', '.m4a', '.aac']
    audio_files = []
    for ext in audio_extensions:
        audio_files.extend(input_dir.glob(f'*{ext}'))
    
    if not audio_files:
        print("No audio files found")
        return
    
    print(f"Found {len(audio_files)} audio files")
    
    # Process each file
    handler = AudioFormatHandler()
    processor = voice_processor.VoiceProcessor()
    
    if args.preset:
        processor.load_preset(args.preset)
    
    for i, input_file in enumerate(audio_files, 1):
        try:
            print(f"[{i}/{len(audio_files)}] Processing {input_file.name}")
            
            # Load audio
            audio_data, metadata = handler.load_audio(str(input_file))
            
            # Process
            processed = processor.process_chunk(audio_data)
            
            # Determine output file
            output_file = output_dir / input_file.name
            if args.format:
                output_file = output_file.with_suffix(f'.{args.format}')
            
            # Save
            handler.save_audio(processed, str(output_file),
                              sample_rate=metadata.get('sample_rate', 44100),
                              channels=metadata.get('channels', 1))
            
        except Exception as e:
            print(f"  Error: {e}")
            continue
    
    print(f"Batch processing complete. Output saved to {output_dir}")

def process_optimize(args):
    """Process file optimization"""
    print(f"Optimizing {args.input} -> {args.output} (level: {args.level})")
    
    try:
        # Check if input is a file or directory
        input_path = Path(args.input)
        output_path = Path(args.output)
        
        optimizer = file_optimizer.AudioOptimizer()
        
        if input_path.is_file():
            # Single file optimization
            success = optimizer.optimize_file(str(input_path), str(output_path), args.level)
            if success:
                # Show results
                original_size = input_path.stat().st_size
                new_size = output_path.stat().st_size if output_path.exists() else original_size
                compression = (original_size - new_size) / original_size * 100 if original_size > 0 else 0
                
                print(f"Original size: {original_size:,} bytes")
                print(f"Optimized size: {new_size:,} bytes")
                print(f"Compression: {compression:.1f}%")
            else:
                print("Optimization failed")
        
        elif input_path.is_dir():
            # Batch optimization
            results = optimizer.batch_optimize(str(input_path), str(output_path), args.level)
            
            if 'error' in results:
                print(f"Error: {results['error']}")
                return
            
            print(f"Processed {results['processed']} files")
            print(f"Failed: {results['failed']} files")
            
            if results['total_size_before'] > 0:
                compression = results.get('overall_compression_percent', 0)
                print(f"Total original size: {results['total_size_before']:,} bytes")
                print(f"Total optimized size: {results['total_size_after']:,} bytes")
                print(f"Overall compression: {compression:.1f}%")
        
        else:
            print(f"Input path not found: {args.input}")
    
    except Exception as e:
        print(f"Optimization error: {e}")

def process_plugins(args):
    """Process with audio plugins"""
    try:
        from plugin_sdk import PluginManager
        from plugin_examples import EXAMPLE_PLUGINS
        
        # Initialize plugin manager
        plugin_mgr = PluginManager()
        
        # Register example plugins
        for name, plugin_class in EXAMPLE_PLUGINS.items():
            plugin_mgr.plugin_classes[name] = plugin_class
            instance = plugin_class()
            plugin_mgr.plugin_infos[name] = instance.get_info()
        
        if args.plugin_action == 'list':
            print("Available Plugins:")
            print("=" * 50)
            
            plugins = plugin_mgr.list_plugins()
            for name, details in plugins.items():
                info = details["info"]
                loaded = "✓" if details["loaded"] else " "
                active = "●" if details["active"] else "○"
                
                print(f"{loaded} {active} {name} v{info.version}")
                print(f"    Type: {info.plugin_type.value}")
                print(f"    Category: {info.category.value}")
                print(f"    Description: {info.description}")
                print(f"    Author: {info.author}")
                if info.tags:
                    print(f"    Tags: {', '.join(info.tags)}")
                print()
        
        elif args.plugin_action == 'apply':
            print(f"Applying plugins to {args.input}")
            
            # Load audio
            handler = AudioFormatHandler()
            audio_data, metadata = handler.load_audio(args.input)
            sample_rate = metadata.get('sample_rate', 44100)
            
            # Convert audio data to float samples
            if isinstance(audio_data, bytes):
                # Convert bytes to samples
                import array
                arr = array.array('h')
                arr.frombytes(audio_data)
                float_samples = [s / 32768.0 for s in arr]
            elif isinstance(audio_data, list):
                float_samples = audio_data
            else:
                float_samples = list(audio_data)
            
            # Process through plugins
            if args.chain:
                # Use named chain
                processed = plugin_mgr.apply_effect_chain(float_samples, args.chain, sample_rate=sample_rate)
            elif args.plugins:
                # Load and enable plugins
                for plugin_name in args.plugins:
                    if plugin_mgr.load_plugin(plugin_name):
                        plugin_mgr.enable_plugin(plugin_name)
                
                # Process through plugin chain
                processed = plugin_mgr.process_through_plugins(float_samples, args.plugins, sample_rate=sample_rate)
            else:
                processed = float_samples
                print("No plugins specified")
            
            # Convert back to audio format
            if isinstance(processed, list):
                # Convert float samples back to int16
                import array
                int_samples = [int(max(-32768, min(32767, s * 32767))) for s in processed]
                arr = array.array('h', int_samples)
                output_data = arr.tobytes()
            else:
                output_data = processed
            
            # Save output
            handler.save_audio(output_data, args.output,
                              sample_rate=sample_rate,
                              channels=metadata.get('channels', 1))
            
            print(f"Applied plugins: {', '.join(args.plugins) if args.plugins else args.chain}")
            print(f"Saved to {args.output}")
        
        elif args.plugin_action == 'create':
            from plugin_sdk import PluginDeveloperKit
            
            kit = PluginDeveloperKit()
            success = kit.create_plugin_project(args.name, args.type, args.output_dir)
            
            if success:
                print(f"Created plugin project: {args.name}")
            else:
                print(f"Failed to create plugin project")
        
        elif args.plugin_action == 'demo':
            from plugin_sdk import demo_plugin_system
            demo_plugin_system()
        
        elif args.plugin_action == 'load':
            success = plugin_mgr.load_plugin_from_file(args.file)
            if success:
                print(f"Loaded plugin from: {args.file}")
            else:
                print(f"Failed to load plugin from: {args.file}")
        
        elif args.plugin_action == 'generate':
            # Load generator plugin
            if plugin_mgr.load_plugin(args.generator):
                plugin_mgr.enable_plugin(args.generator)
                
                # Set parameters if provided
                if args.params:
                    params = json.loads(args.params)
                    for key, value in params.items():
                        plugin_mgr.set_plugin_parameter(args.generator, key, value)
                
                # Generate audio
                generated = plugin_mgr.process_through_plugins(
                    None, 
                    [args.generator],
                    duration=args.duration,
                    sample_rate=44100
                )
                
                if generated:
                    # Convert to audio format and save
                    import array
                    int_samples = [int(max(-32768, min(32767, s * 32767))) for s in generated]
                    arr = array.array('h', int_samples)
                    output_data = arr.tobytes()
                    
                    handler = AudioFormatHandler()
                    handler.save_audio(output_data, args.output, sample_rate=44100, channels=1)
                    
                    print(f"Generated {args.duration}s of audio using {args.generator}")
                    print(f"Saved to {args.output}")
                else:
                    print("Failed to generate audio")
            else:
                print(f"Failed to load generator plugin: {args.generator}")
        
        else:
            print(f"Unknown plugin action: {args.plugin_action}")
    
    except Exception as e:
        print(f"Plugin processing error: {e}")
        import traceback
        traceback.print_exc()

def process_quality(args):
    """Process audio quality analysis and correction"""
    print(f"Analyzing quality of {args.input}")
    
    try:
        # Load audio
        handler = AudioFormatHandler()
        audio_data, metadata = handler.load_audio(args.input)
        
        if args.analyze_only:
            # Analysis only
            metrics = quality_monitor.check_quality(audio_data)
            
            print(f"\nQuality Analysis Results:")
            print(f"  Overall Quality Score: {metrics.quality_score:.1f}/100")
            print(f"  Peak Level: {metrics.peak_level:.3f} ({metrics.peak_level*100:.1f}%)")
            print(f"  RMS Level: {metrics.rms_level:.3f} ({metrics.rms_level*100:.1f}%)")
            print(f"  Dynamic Range: {metrics.dynamic_range:.3f}")
            print(f"  SNR Estimate: {metrics.snr_estimate:.1f} dB")
            print(f"  THD Estimate: {metrics.thd_estimate:.2f}%")
            print(f"  DC Offset: {metrics.dc_offset:.1f}")
            print(f"  Clipping Detected: {'Yes' if metrics.clipping_detected else 'No'}")
            print(f"  Silent: {'Yes' if metrics.is_silent else 'No'}")
            
            # Recommendations
            monitor = quality_monitor.QualityMonitor()
            monitor.analyze_quality(audio_data)  # Add to history
            report = monitor.get_quality_report()
            
            print(f"\nRecommendations:")
            for rec in report.get('recommendations', []):
                print(f"  - {rec}")
        
        else:
            # Analysis and correction
            if not args.output:
                print("Output file required for correction")
                return
            
            corrected_audio, correction_info = quality_monitor.process_with_quality_control(
                audio_data, args.target_quality
            )
            
            # Save corrected audio
            handler.save_audio(corrected_audio, args.output,
                              sample_rate=metadata.get('sample_rate', 44100),
                              channels=metadata.get('channels', 1))
            
            print(f"\nQuality Correction Results:")
            print(f"  Initial Quality: {correction_info['initial_quality']:.1f}/100")
            print(f"  Final Quality: {correction_info['final_quality']:.1f}/100")
            print(f"  Improvement: {correction_info.get('improvement', 0):.1f} points")
            print(f"  Corrections Applied: {', '.join(correction_info.get('corrections_applied', []))}")
            print(f"  Output saved to: {args.output}")
    
    except Exception as e:
        print(f"Quality processing error: {e}")

def process_convert(args):
    """Process format conversion"""
    print(f"Converting {args.input} -> {args.output}")
    
    try:
        # Load audio
        handler = AudioFormatHandler()
        audio_data, metadata = handler.load_audio(args.input)
        
        # Prepare conversion parameters
        output_sample_rate = args.sample_rate_out or metadata.get('sample_rate', 44100)
        output_channels = metadata.get('channels', 1)
        
        # Apply sample rate conversion if needed
        if output_sample_rate != metadata.get('sample_rate', 44100):
            samples = audio_utils.bytes_to_samples(audio_data)
            resampled = audio_utils.resample_linear(
                samples, 
                metadata.get('sample_rate', 44100), 
                output_sample_rate
            )
            audio_data = audio_utils.samples_to_bytes(resampled)
            print(f"  Sample rate: {metadata.get('sample_rate', 44100)} -> {output_sample_rate} Hz")
        
        # Apply quality-based processing
        if args.quality == 'high':
            # High quality: apply enhancement
            audio_data = quality_monitor.enhance_audio(audio_data)
            print("  Applied high-quality enhancement")
        elif args.quality == 'low':
            # Low quality: simple processing
            pass
        else:  # medium
            # Medium quality: normalize
            audio_data = audio_utils.normalize_audio(audio_data, 0.9)
            print("  Applied normalization")
        
        # Save converted audio
        success = handler.save_audio(audio_data, args.output,
                                   sample_rate=output_sample_rate,
                                   channels=output_channels)
        
        if success:
            # Show file info
            input_info = audio_utils.get_file_info(args.input)
            output_info = audio_utils.get_file_info(args.output)
            
            print(f"Conversion completed:")
            print(f"  Input:  {input_info.get('size_mb', 0):.2f} MB, {metadata.get('sample_rate', 0)} Hz")
            print(f"  Output: {output_info.get('size_mb', 0):.2f} MB, {output_sample_rate} Hz")
        else:
            print("Conversion failed")
    
    except Exception as e:
        print(f"Conversion error: {e}")


def process_detect(args):
    """Process audio format detection command"""
    try:
        if not os.path.exists(args.input):
            print(f"Error: Input file not found: {args.input}")
            return
        
        print(f"Analyzing audio file: {args.input}")
        print("-" * 50)
        
        # Detect format
        detection = audio_detector.detect_audio_format(args.input)
        
        # Basic information
        print(f"Detected Format: {detection['format'].upper()}")
        print(f"Confidence: {detection['confidence']:.1%}")
        
        if 'detected_by' in detection:
            print(f"Detection Method: {detection['detected_by']}")
        
        # Technical details
        if detection.get('sample_rate'):
            print(f"Sample Rate: {detection['sample_rate']} Hz")
        
        if detection.get('channels'):
            print(f"Channels: {detection['channels']}")
        
        if detection.get('duration'):
            print(f"Duration: {detection['duration']:.2f} seconds")
        
        if detection.get('bitrate'):
            print(f"Bitrate: {detection['bitrate']:,} bps")
        
        # File information
        file_info = audio_utils.get_file_info(args.input)
        print(f"File Size: {file_info.get('size_mb', 0):.2f} MB")
        
        # Detailed analysis
        if args.detailed:
            print("\nDetailed Analysis:")
            print("-" * 30)
            
            # Format support status
            handler = AudioFormatHandler()
            ext = f".{detection['format']}"
            if ext in handler.supported_formats:
                print(f"✓ Format is supported for loading")
            else:
                print(f"✗ Format requires external tools")
            
            if ext in handler.export_formats:
                print(f"✓ Format is supported for export")
            else:
                print(f"✗ Export not supported")
            
            # ffmpeg requirement
            if ext in ['.mp3', '.flac', '.ogg', '.m4a', '.aac', '.wma']:
                if handler.has_ffmpeg:
                    print("✓ FFmpeg available for processing")
                else:
                    print("✗ FFmpeg required but not found")
            
            # Quality estimation
            if audio_detector.is_audio_file(args.input):
                print("✓ File appears to be a valid audio file")
                
                # Try to get quality metrics if possible
                try:
                    # Load audio and analyze quality
                    audio_data, metadata = handler.load_audio(args.input, auto_detect=True)
                    quality_metrics = quality_monitor.check_quality(audio_data)
                    
                    print(f"Quality Score: {quality_metrics.quality_score:.1f}/100")
                    print(f"Peak Level: {quality_metrics.peak_level:.3f}")
                    print(f"RMS Level: {quality_metrics.rms_level:.3f}")
                    print(f"SNR Estimate: {quality_metrics.snr_estimate:.1f} dB")
                    
                    if quality_metrics.clipping_detected:
                        print("⚠ Clipping detected in audio")
                    
                    if quality_metrics.is_silent:
                        print("⚠ Audio appears to be silent")
                    
                except Exception as e:
                    print(f"Note: Could not analyze audio quality: {e}")
            else:
                print("⚠ File may not be a valid audio file")
        
        # Recommendations
        if detection['confidence'] < 0.8:
            print(f"\nNote: Low confidence detection. File may be corrupted or unusual format.")
        
        if 'error' in detection:
            print(f"Warning: {detection['error']}")
    
    except Exception as e:
        print(f"Detection error: {e}")


def list_presets(args):
    """List available voice presets"""
    print("Available Voice Presets:")
    print("=" * 40)
    
    # Get presets from voice processor
    processor = voice_processor.VoiceProcessor()
    
    presets = {
        'normal': 'Default/natural voice (no processing)',
        'male': 'Lower pitch, enhanced masculine formants',
        'female': 'Higher pitch, enhanced feminine formants',
        'child': 'High pitch, playful tone',
        'robot': 'Synthetic/robotic voice effect',
        'deep': 'Very low pitch, bass-heavy',
        'cartoon': 'Exaggerated pitch variations, animated style'
    }
    
    if args.detailed:
        for preset, description in presets.items():
            print(f"\n{preset.upper()}:")
            print(f"  Description: {description}")
            
            # Load preset and show parameters
            if processor.load_preset(preset):
                profile = processor.profile
                print(f"  Parameters:")
                print(f"    Pitch Factor: {profile.pitch}")
                print(f"    Formant Factor: {profile.formant}")
                print(f"    Speed Factor: {profile.speed}")
                print(f"    Gender Shift: {profile.gender}")
            else:
                print(f"  Note: Could not load preset details")
    else:
        # Simple list
        for preset, description in presets.items():
            print(f"  {preset:<10} - {description}")
    
    print(f"\nUsage: python3 main.py voice input.wav output.wav --preset PRESET_NAME")


def process_spectrum(args):
    """Process spectrum analysis command"""
    try:
        import spectrum_analyzer
        
        print(f"Analyzing spectrum of {args.input}")
        result = spectrum_analyzer.analyze_audio_spectrum(args.input, args.detailed)
        
        if 'error' in result:
            print(f"Error: {result['error']}")
            return
        
        print("\nSpectrum Analysis Results:")
        print("=" * 50)
        print(f"Sample Rate: {result['sample_rate']} Hz")
        print(f"Duration: {result['duration']:.2f} seconds")
        print(f"Fundamental Frequency: {result['fundamental_frequency']:.1f} Hz ({result['pitch_note']})")
        print(f"Tempo: {result['tempo_bpm']:.1f} BPM")
        print(f"Spectral Centroid: {result['spectral_centroid']:.1f} Hz")
        print(f"Spectral Spread: {result['spectral_spread']:.1f} Hz")
        
        print("\nDominant Frequencies:")
        for freq, mag in result['dominant_frequencies']:
            print(f"  {freq:.1f} Hz: {mag:.4f}")
        
        print("\nFrequency Bands:")
        for band, energy in result['frequency_bands'].items():
            bar_length = int(energy * 30)
            bar = '█' * bar_length + '░' * (30 - bar_length)
            print(f"  {band:<12}: [{bar}] {energy:.4f}")
        
        if args.detailed and 'harmonics' in result:
            print("\nHarmonics:")
            for harmonic in result['harmonics']:
                print(f"  {harmonic:.1f} Hz")
            
            if 'rhythm_regularity' in result:
                print(f"\nRhythm Regularity: {result['rhythm_regularity']:.2%}")
    
    except Exception as e:
        print(f"Spectrum analysis error: {e}")


def process_record(args):
    """Process audio recording command"""
    try:
        import audio_recorder
        from datetime import datetime
        
        # Generate default filename if not provided
        if not args.output:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            args.output = f"recording_{timestamp}.wav"
        
        print("Starting audio recording...")
        print("=" * 50)
        
        # Record audio
        result = audio_recorder.record_audio(
            duration=args.duration,
            filename=args.output,
            auto_stop_silence=args.auto_stop
        )
        
        if result:
            print(f"\n✓ Recording completed successfully")
            print(f"  File: {result}")
            
            # Optionally analyze the recording
            try:
                import audio_utils
                info = audio_utils.get_file_info(result)
                print(f"  Size: {info.get('size_mb', 0):.2f} MB")
                print(f"  Duration: {info.get('duration', 0):.2f} seconds")
            except:
                pass
        else:
            print("\n✗ Recording failed or cancelled")
    
    except Exception as e:
        print(f"Recording error: {e}")


def process_denoise(args):
    """Process audio denoising command"""
    try:
        import noise_reducer
        
        print(f"Processing noise reduction: {args.input} -> {args.output}")
        print("=" * 50)
        
        # Process audio enhancement
        success = noise_reducer.process_audio_enhancement(
            args.input, 
            args.output,
            noise_reduction=args.noise_reduction,
            clarity_enhancement=args.clarity,
            remove_clicks=True,
            apply_compression=args.compress
        )
        
        if success:
            print("\n✓ Audio enhancement completed")
            
            # Show file size comparison
            try:
                import audio_utils
                input_info = audio_utils.get_file_info(args.input)
                output_info = audio_utils.get_file_info(args.output)
                
                print(f"  Input:  {input_info.get('size_mb', 0):.2f} MB")
                print(f"  Output: {output_info.get('size_mb', 0):.2f} MB")
            except:
                pass
        else:
            print("\n✗ Audio enhancement failed")
    
    except Exception as e:
        print(f"Denoising error: {e}")


def process_interactive(args):
    """Process interactive mode command"""
    try:
        import interactive_mode
        
        print("Starting Interactive Mode")
        print("=" * 50)
        print("Controls:")
        print("  W/S: Navigate parameters")
        print("  A/D: Adjust values")
        print("  R: Reset  Space: Toggle")
        print("  Q: Quit")
        print()
        
        # Start interactive mode
        interactive_mode.run_interactive_mode(args.input)
        
    except Exception as e:
        print(f"Interactive mode error: {e}")


def process_visualize(args):
    """Process visualization command"""
    try:
        import audio_visualizer
        
        print(f"Visualizing: {args.input}")
        print(f"Style: {args.style}")
        print("Press Ctrl+C to stop")
        print()
        
        # Run visualization
        audio_visualizer.visualize_audio_file(
            args.input,
            style=args.style,
            duration=args.duration
        )
        
    except Exception as e:
        print(f"Visualization error: {e}")


def process_mix(args):
    """Process multi-track mixing command"""
    try:
        import audio_mixer
        
        print(f"Mixing {len(args.tracks)} tracks -> {args.output}")
        print("=" * 50)
        
        # Prepare mix settings
        mix_settings = {
            'master_volume': args.master_volume,
            'master_limiter': True
        }
        
        # Add track settings if provided
        if args.volumes:
            for i, volume in enumerate(args.volumes):
                if i < len(args.tracks):
                    mix_settings[f'track_{i}'] = mix_settings.get(f'track_{i}', {})
                    mix_settings[f'track_{i}']['volume'] = volume
        
        if args.pans:
            for i, pan in enumerate(args.pans):
                if i < len(args.tracks):
                    mix_settings[f'track_{i}'] = mix_settings.get(f'track_{i}', {})
                    mix_settings[f'track_{i}']['pan'] = pan
        
        # Create mix
        audio_mixer.create_multitrack_mix(
            args.tracks,
            args.output,
            mix_settings
        )
        
        print("\n✓ Mix completed successfully")
        
    except Exception as e:
        print(f"Mixing error: {e}")


def process_script(args):
    """Process audio scripting command"""
    try:
        import audio_scripting
        
        if args.action == 'create':
            if not all([args.template, args.input, args.output]):
                print("Error: --template, --input, and --output are required for create action")
                return
            
            print(f"Creating script from template: {args.template}")
            script_file = audio_scripting.create_processing_script(
                args.template, args.input, args.output
            )
            
            if script_file:
                print(f"✓ Script created: {script_file}")
                
                # Optionally execute immediately
                engine = audio_scripting.AudioScriptEngine()
                if engine.load_script(script_file):
                    print("Execute script now? [y/N]")
                    if input().lower().startswith('y'):
                        engine.execute_script(script_file)
            else:
                print("✗ Failed to create script")
        
        elif args.action == 'execute':
            if not args.script_file:
                print("Error: --script-file is required for execute action")
                return
            
            engine = audio_scripting.AudioScriptEngine()
            if engine.load_script(args.script_file):
                success = engine.execute_script(args.script_file)
                
                # Show execution report
                report = engine.get_execution_report()
                if report:
                    print(f"\nExecution Summary:")
                    print(f"  Status: {report['status']}")
                    print(f"  Success Rate: {report['success_rate']:.1f}%")
                    print(f"  Duration: {report.get('duration', 0):.1f}s")
            else:
                print(f"✗ Failed to load script: {args.script_file}")
        
        elif args.action == 'templates':
            engine = audio_scripting.AudioScriptEngine()
            templates = engine.list_templates()
            
            print("Available Script Templates:")
            print("=" * 40)
            for template_name in templates:
                info = engine.get_template_info(template_name)
                print(f"{template_name}:")
                print(f"  Description: {info['description']}")
                print(f"  Tasks: {len(info['tasks'])}")
                for task in info['tasks']:
                    print(f"    - {task['id']}: {task['command']}")
                print()
    
    except Exception as e:
        print(f"Scripting error: {e}")


def process_pipeline(args):
    """Process format conversion pipeline command"""
    try:
        import format_pipeline
        
        if args.action == 'convert':
            if not all([args.input, args.output]):
                print("Error: --input and --output are required for convert action")
                return
            
            print(f"Converting {args.input} -> {args.output}")
            print(f"Profile: {args.profile}")
            
            success = format_pipeline.convert_with_pipeline(
                args.input, args.output, args.profile
            )
            
            if success:
                print("✓ Conversion completed successfully")
            else:
                print("✗ Conversion failed")
        
        elif args.action == 'batch':
            if not all([args.input, args.output]):
                print("Error: --input and --output directories are required for batch action")
                return
            
            print(f"Batch converting: {args.input} -> {args.output}")
            print(f"Profile: {args.profile}")
            
            with format_pipeline.FormatPipeline() as pipeline:
                results = pipeline.batch_convert(
                    args.input, args.output, args.profile
                )
                
                successful = sum(1 for success in results.values() if success)
                print(f"\nBatch conversion summary:")
                print(f"  Successful: {successful}/{len(results)}")
        
        elif args.action == 'profiles':
            pipeline = format_pipeline.FormatPipeline()
            profiles = pipeline.list_profiles()
            
            print("Available Conversion Profiles:")
            print("=" * 40)
            for profile_name in profiles:
                info = pipeline.get_profile_info(profile_name)
                print(f"{profile_name}:")
                print(f"  Format: {info['format']}")
                print(f"  Quality: {info['quality']}")
                if info['bitrate']:
                    print(f"  Bitrate: {info['bitrate']} kbps")
                print(f"  Sample Rate: {info['sample_rate']} Hz")
                print(f"  Channels: {info['channels']}")
                print()
    
    except Exception as e:
        print(f"Pipeline error: {e}")


def process_restore(args):
    """Process audio restoration command"""
    try:
        import audio_restoration
        
        if args.action == 'repair':
            if not all([args.input, args.output]):
                print("Error: --input and --output are required for repair action")
                return
            
            print(f"Restoring audio: {args.input} -> {args.output}")
            print(f"Profile: {args.profile}")
            
            success = audio_restoration.restore_audio_file(
                args.input, args.output, args.profile
            )
            
            if success:
                print("✓ Audio restoration completed successfully")
            else:
                print("✗ Audio restoration failed")
        
        elif args.action == 'analyze':
            if not args.input:
                print("Error: --input is required for analyze action")
                return
            
            import wave
            
            print(f"Analyzing audio problems: {args.input}")
            print("=" * 50)
            
            # Load and analyze audio
            with wave.open(args.input, 'rb') as wav:
                audio_data = wav.readframes(wav.getnframes())
                sample_rate = wav.getframerate()
            
            restorer = audio_restoration.AudioRestoration(sample_rate)
            analysis = restorer.analyze_audio_problems(audio_data)
            
            print(f"Clipping: {analysis['clipping_percentage']:.1f}%")
            print(f"DC Offset: {analysis['dc_offset']:.4f}")
            print(f"Noise Level: {analysis['noise_level']:.4f}")
            print(f"Dropouts: {analysis['dropouts_detected']}")
            print(f"Dynamic Range: {analysis['dynamic_range']:.1f} dB")
            
            if analysis['recommendations']:
                print("\nRecommendations:")
                for rec in analysis['recommendations']:
                    print(f"  - {rec}")
            else:
                print("\n✓ No major problems detected")
        
        elif args.action == 'profiles':
            restorer = audio_restoration.AudioRestoration()
            profiles = restorer.list_profiles()
            
            print("Available Restoration Profiles:")
            print("=" * 40)
            for profile_name in profiles:
                info = restorer.get_profile_info(profile_name)
                print(f"{profile_name}:")
                print(f"  Description: {info.description}")
                print(f"  Algorithms: {', '.join(info.algorithms)}")
                print()
    
    except Exception as e:
        print(f"Restoration error: {e}")

def process_synthesize(args):
    """Process audio synthesis command"""
    try:
        synthesizer = AudioSynthesizer()
        
        if args.action == 'demo':
            print("🎵 Running synthesis demo...")
            results = demo_synthesis()
            
            print("Demo complete. Generated samples:")
            for name, audio in results.items():
                output_file = f"demo_{name}.wav"
                synthesizer.save_audio(audio, output_file)
                print(f"  {name}: {output_file} ({len(audio)/synthesizer.sample_rate:.1f}s)")
            return
        
        if not args.output:
            print("Error: --output is required for synthesis actions")
            return
        
        # Map waveform string to enum
        waveform_map = {
            'sine': WaveformType.SINE,
            'sawtooth': WaveformType.SAWTOOTH,
            'square': WaveformType.SQUARE,
            'triangle': WaveformType.TRIANGLE,
            'noise': WaveformType.NOISE
        }
        waveform = waveform_map.get(args.waveform, WaveformType.SINE)
        
        if args.action == 'tone':
            print(f"Generating {args.waveform} tone: {args.frequency}Hz, {args.duration}s")
            audio = synthesizer.generate_tone(
                args.frequency, args.duration, waveform, args.amplitude
            )
            
        elif args.action == 'chord':
            if not args.frequencies:
                # Default C major chord
                frequencies = [261.63, 329.63, 392.00]  # C, E, G
                print("Using default C major chord")
            else:
                frequencies = args.frequencies
            
            print(f"Generating chord: {frequencies}")
            audio = synthesizer.generate_chord(frequencies, args.duration, waveform, args.amplitude)
            
        elif args.action == 'arpeggio':
            if not args.frequencies:
                # Default C major arpeggio
                frequencies = [261.63, 329.63, 392.00, 523.25]  # C, E, G, C
                print("Using default C major arpeggio")
            else:
                frequencies = args.frequencies
            
            print(f"Generating arpeggio: {frequencies}")
            audio = synthesizer.generate_arpeggio(frequencies, args.duration)
            
        elif args.action == 'drums':
            print(f"Generating drum pattern: {args.bpm} BPM, {args.duration}s")
            audio = synthesizer.generate_drum_pattern(args.duration, args.bpm)
            
        elif args.action == 'sequence':
            if not args.sequence_file:
                print("Error: --sequence-file is required for sequence action")
                return
            
            try:
                import json
                with open(args.sequence_file, 'r') as f:
                    sequence_data = json.load(f)
                
                print(f"Generating sequence from: {args.sequence_file}")
                audio = synthesizer.generate_sequence(sequence_data, args.duration)
            except FileNotFoundError:
                print(f"Error: Sequence file not found: {args.sequence_file}")
                return
            except json.JSONDecodeError:
                print(f"Error: Invalid JSON in sequence file: {args.sequence_file}")
                return
        else:
            print(f"Unknown synthesis action: {args.action}")
            return
        
        # Save audio
        synthesizer.save_audio(audio, args.output)
        print(f"✓ Synthesis complete: {args.output}")
        print(f"  Duration: {len(audio)/synthesizer.sample_rate:.1f}s")
        print(f"  Samples: {len(audio)}")
        
    except Exception as e:
        print(f"Synthesis error: {e}")

def process_spatial(args):
    """Process spatial audio command"""
    try:
        # モード変換
        mode_map = {
            'stereo': SpatialMode.STEREO,
            'binaural': SpatialMode.BINAURAL,
            'surround_5_1': SpatialMode.SURROUND_5_1,
            'surround_7_1': SpatialMode.SURROUND_7_1
        }
        spatial_mode = mode_map.get(args.mode, SpatialMode.BINAURAL)
        
        processor = SpatialAudioProcessor(mode=spatial_mode)
        
        if args.action == 'demo':
            print("🎵 Running spatial audio demo...")
            results = demo_spatial_audio()
            
            # デモ結果保存
            for pos_name, (left, right) in results['positioned'].items():
                output_file = f"spatial_demo_{pos_name}.wav"
                channels = {'left': left, 'right': right}
                processor.save_multichannel_audio(channels, output_file)
                print(f"  {pos_name}: {output_file}")
                
            # サラウンドミックス保存
            if results['surround']:
                processor.save_multichannel_audio(results['surround'], "spatial_demo_surround.wav")
                print(f"  surround: spatial_demo_surround.wav")
                
            # ルームシミュレーション保存
            if results['room']:
                channels = {'mono': results['room']}
                processor.save_multichannel_audio(channels, "spatial_demo_room.wav")
                print(f"  room: spatial_demo_room.wav")
            return
        
        if not args.input or not args.output:
            print("Error: --input and --output are required for spatial processing")
            return
        
        # 音声ファイル読み込み
        handler = AudioFormatHandler()
        audio_data, metadata = handler.load_audio(args.input)
        
        if args.action == 'position':
            print(f"Applying 3D positioning: {args.position}")
            
            # 位置オブジェクト作成
            position = Position3D(args.position[0], args.position[1], args.position[2])
            listener_pos = Position3D(args.listener[0], args.listener[1], args.listener[2])
            
            # 空間処理
            left_output, right_output = processor.process_positioned_audio(
                audio_data, position, listener_pos
            )
            
            # バイノーラル出力として保存
            channels = {'left': left_output, 'right': right_output}
            processor.save_multichannel_audio(channels, args.output)
            
        elif args.action == 'surround':
            if not args.sources_file:
                print("Error: --sources-file is required for surround action")
                return
                
            try:
                import json
                with open(args.sources_file, 'r') as f:
                    sources_data = json.load(f)
                
                print(f"Creating surround mix from: {args.sources_file}")
                
                # ソース読み込み
                sources = {}
                for source_name, source_info in sources_data.items():
                    if 'file' in source_info and 'position' in source_info:
                        src_audio, _ = handler.load_audio(source_info['file'])
                        pos = source_info['position']
                        position = Position3D(pos[0], pos[1], pos[2])
                        sources[source_name] = (src_audio, position)
                
                # サラウンドミックス作成
                surround_mix = processor.create_surround_mix(sources)
                processor.save_multichannel_audio(surround_mix, args.output)
                
            except FileNotFoundError:
                print(f"Error: Sources file not found: {args.sources_file}")
                return
            except json.JSONDecodeError:
                print(f"Error: Invalid JSON in sources file: {args.sources_file}")
                return
                
        elif args.action == 'room':
            print(f"Applying room simulation: size={args.room_size}m, damping={args.damping}")
            
            room_audio = processor.apply_room_simulation(
                audio_data, args.room_size, args.damping
            )
            
            # モノラル出力として保存
            channels = {'mono': room_audio}
            processor.save_multichannel_audio(channels, args.output)
            
        else:
            print(f"Unknown spatial action: {args.action}")
            return
        
        print(f"✓ Spatial processing complete: {args.output}")
        print(f"  Mode: {args.mode}")
        print(f"  Action: {args.action}")
        
    except Exception as e:
        print(f"Spatial processing error: {e}")

def process_ml(args):
    """Process machine learning command"""
    try:
        processor = MLAudioProcessor()
        
        if args.action == 'demo':
            print("🤖 Running machine learning audio demo...")
            results = demo_ml_audio()
            
            if args.output:
                import json
                with open(args.output, 'w') as f:
                    # Enum値をシリアライズ可能に変換
                    serializable_results = {}
                    for name, result in results.items():
                        serializable_results[name] = convert_enums_to_strings(result)
                    json.dump(serializable_results, f, indent=2)
                print(f"Demo results saved to: {args.output}")
            return
        
        if not args.input:
            print("Error: --input is required for ML processing")
            return
        
        # 音声ファイル読み込み
        handler = AudioFormatHandler()
        audio_data, metadata = handler.load_audio(args.input)
        
        if args.action == 'analyze':
            print(f"Comprehensive ML analysis: {args.input}")
            
            analysis = processor.analyze_audio_comprehensive(audio_data)
            
            # 結果表示
            print(f"\n=== Analysis Results ===")
            print(f"Duration: {analysis['basic_stats']['duration']:.2f}s")
            print(f"Classification: {analysis['classification']['classification'].value}")
            print(f"Confidence: {analysis['classification']['confidence']:.2f}")
            print(f"Emotion: {analysis['emotion_analysis']['predicted_emotion'].value}")
            print(f"Quality Score: {analysis['quality_score']['overall_score']:.1f} ({analysis['quality_score']['grade']})")
            print(f"Segments Found: {len(analysis['segments'])}")
            
            if analysis['quality_score']['issues']:
                print(f"\nIssues Detected:")
                for issue in analysis['quality_score']['issues']:
                    print(f"  - {issue}")
            
            if args.detailed:
                print(f"\n=== Detailed Features ===")
                for feature, value in analysis['features'].items():
                    if isinstance(value, (int, float)):
                        print(f"{feature}: {value:.4f}")
                    elif isinstance(value, list) and len(value) <= 5:
                        print(f"{feature}: {value}")
            
            # JSON出力
            if args.output:
                serializable_analysis = convert_enums_to_strings(analysis)
                import json
                with open(args.output, 'w') as f:
                    json.dump(serializable_analysis, f, indent=2)
                print(f"\nAnalysis saved to: {args.output}")
        
        elif args.action == 'classify':
            print(f"Audio classification: {args.input}")
            
            classification = processor.classifier.classify_audio_type(audio_data)
            print(f"Type: {classification['classification'].value}")
            print(f"Confidence: {classification['confidence']:.2f}")
            print(f"Energy: {classification['energy']:.6f}")
            
            if 'zero_crossing_rate' in classification:
                print(f"Zero Crossing Rate: {classification['zero_crossing_rate']:.4f}")
            if 'spectral_centroid' in classification:
                print(f"Spectral Centroid: {classification['spectral_centroid']:.1f} Hz")
        
        elif args.action == 'emotion':
            print(f"Emotion analysis: {args.input}")
            
            emotion_analysis = processor.classifier.analyze_emotion(audio_data)
            print(f"Predicted Emotion: {emotion_analysis['predicted_emotion'].value}")
            print(f"Confidence: {emotion_analysis['confidence']:.2f}")
            
            if args.detailed:
                print(f"\nEmotion Scores:")
                for emotion, score in emotion_analysis['emotion_scores'].items():
                    print(f"  {emotion.value}: {score:.3f}")
                
                print(f"\nFeatures:")
                for feature, value in emotion_analysis['features'].items():
                    print(f"  {feature}: {value:.4f}")
        
        elif args.action == 'segment':
            print(f"Audio segmentation: {args.input}")
            
            segments = processor.segmenter.segment_by_energy(audio_data, args.threshold)
            print(f"Found {len(segments)} segments:")
            
            for i, segment in enumerate(segments):
                print(f"  Segment {i+1}: {segment['start']:.2f}s - {segment['end']:.2f}s "
                      f"({segment['duration']:.2f}s)")
        
        elif args.action == 'anomaly':
            print(f"Anomaly detection: {args.input}")
            
            anomalies = processor._detect_all_anomalies(audio_data)
            
            print(f"Clipping: {'Yes' if anomalies['clipping']['has_clipping'] else 'No'}")
            if anomalies['clipping']['has_clipping']:
                print(f"  Ratio: {anomalies['clipping']['clipping_ratio']:.4f}")
                print(f"  Severity: {anomalies['clipping']['severity']}")
            
            print(f"DC Offset: {'Yes' if anomalies['dc_offset']['has_dc_offset'] else 'No'}")
            if anomalies['dc_offset']['has_dc_offset']:
                print(f"  Offset: {anomalies['dc_offset']['dc_offset']:.4f}")
                print(f"  Severity: {anomalies['dc_offset']['severity']}")
            
            print(f"High Noise: {'Yes' if anomalies['noise']['is_noisy'] else 'No'}")
            print(f"  Noise Level: {anomalies['noise']['noise_level']:.4f}")
            print(f"  Severity: {anomalies['noise']['severity']}")
        
        # 特徴量エクスポート
        if args.export_features and args.action in ['analyze', 'classify']:
            print(f"Exporting features to: {args.export_features}")
            export_features_csv(processor, audio_data, args.export_features)
        
        print(f"✓ ML processing complete")
        
    except Exception as e:
        print(f"ML processing error: {e}")

def convert_enums_to_strings(obj):
    """Enum値を文字列に変換 (JSON シリアライズ用)"""
    if hasattr(obj, 'value'):  # Enum
        return obj.value
    elif isinstance(obj, dict):
        return {key: convert_enums_to_strings(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_enums_to_strings(item) for item in obj]
    else:
        return obj

def export_features_csv(processor, audio_data, filename):
    """特徴量をCSVエクスポート"""
    try:
        # bytes型の場合はfloatリストに変換
        if isinstance(audio_data, bytes):
            audio_list = []
            for i in range(0, len(audio_data), 2):
                if i + 1 < len(audio_data):
                    sample = struct.unpack('<h', audio_data[i:i+2])[0]
                    audio_list.append(sample / 32767.0)
            audio_data = audio_list
        
        features = processor._extract_all_features(audio_data)
        
        with open(filename, 'w') as f:
            f.write("feature,value\n")
            for feature, value in features.items():
                if isinstance(value, (int, float)):
                    f.write(f"{feature},{value}\n")
                elif isinstance(value, list):
                    for i, v in enumerate(value):
                        f.write(f"{feature}_{i},{v}\n")
        
        print(f"Features exported to: {filename}")
        
    except Exception as e:
        print(f"Feature export error: {e}")

def process_stream(args):
    """Process network streaming command"""
    try:
        # 品質マッピング
        quality_map = {
            'low': StreamingQuality.LOW,
            'medium': StreamingQuality.MEDIUM,
            'high': StreamingQuality.HIGH,
            'broadcast': StreamingQuality.BROADCAST
        }
        quality = quality_map.get(args.quality, StreamingQuality.MEDIUM)
        
        # プロトコルマッピング
        protocol_map = {
            'udp_raw': StreamingProtocol.UDP_RAW,
            'tcp_reliable': StreamingProtocol.TCP_RELIABLE
        }
        protocol = protocol_map.get(args.protocol, StreamingProtocol.UDP_RAW)
        
        if args.action == 'demo':
            print("🌐 Running network audio streaming demo...")
            demo_network_audio()
            return
        
        elif args.action == 'server' or args.action == 'broadcast':
            print(f"Starting audio streaming server on {args.host}:{args.port}")
            print(f"Protocol: {args.protocol}, Quality: {args.quality}")
            
            processor = LiveAudioProcessor()
            processor.start_live_stream(args.host, args.port, quality)
            
            if args.input:
                print(f"Streaming file: {args.input}")
                processor.stream_audio_file(args.input)
            else:
                print("Server ready for live streaming...")
                print("Press Ctrl+C to stop")
                try:
                    while True:
                        time.sleep(1)
                except KeyboardInterrupt:
                    pass
            
            processor.stop_live_processing()
            
        elif args.action == 'client' or args.action == 'receive':
            print(f"Connecting to audio stream at {args.host}:{args.port}")
            print(f"Protocol: {args.protocol}, Quality: {args.quality}")
            
            processor = LiveAudioProcessor()
            processor.start_live_receive(args.host, args.port, quality)
            
            # 受信音声保存用
            received_audio = []
            
            def save_audio_callback(audio_data):
                received_audio.extend(audio_data)
                
            if args.output:
                processor.receiver.set_audio_callback(save_audio_callback)
            
            print(f"Receiving for {args.duration} seconds...")
            
            start_time = time.time()
            last_report_time = start_time
            
            while time.time() - start_time < args.duration:
                time.sleep(0.1)
                
                # 品質監視表示
                if args.monitor and processor.receiver:
                    current_time = time.time()
                    if current_time - last_report_time >= 2.0:  # 2秒間隔
                        report = processor.receiver.get_quality_report()
                        if report['received_packets'] > 0:
                            print(f"Quality: {report['quality_score']:.1f}/100, "
                                  f"Latency: {report['latency_ms']:.1f}ms, "
                                  f"Packet Loss: {report['packet_loss_rate']:.2%}, "
                                  f"Packets: {report['received_packets']}")
                        last_report_time = current_time
            
            processor.stop_live_processing()
            
            # 受信音声保存
            if args.output and received_audio:
                print(f"Saving received audio to: {args.output}")
                
                # 16bit PCMとして保存
                audio_array = array.array('h', [int(max(-32767, min(32767, sample * 32767))) 
                                               for sample in received_audio])
                
                with wave.open(args.output, 'w') as wav_file:
                    wav_file.setnchannels(1)  # モノラル
                    wav_file.setsampwidth(2)  # 16bit
                    wav_file.setframerate(44100)
                    wav_file.writeframes(audio_array.tobytes())
                    
        else:
            print(f"Unknown streaming action: {args.action}")
            return
        
        print(f"✓ Network streaming complete")
        
    except Exception as e:
        print(f"Network streaming error: {e}")

def process_codec(args):
    """Process advanced codec command"""
    try:
        codec_manager = AdvancedAudioCodecManager()
        
        if args.action == 'demo':
            print("🎵 Running advanced codecs demo...")
            demo_advanced_codecs()
            return
        
        elif args.action == 'encode':
            if not args.input or not args.output:
                print("Error: --input and --output are required for encoding")
                return
            
            print(f"Encoding {args.input} with {args.codec} codec (quality: {args.quality})")
            
            # 音声ファイル読み込み
            handler = AudioFormatHandler()
            audio_data, metadata = handler.load_audio(args.input)
            
            # bytes → float変換
            if isinstance(audio_data, bytes):
                audio_list = []
                for i in range(0, len(audio_data), 2):
                    if i + 1 < len(audio_data):
                        sample = struct.unpack('<h', audio_data[i:i+2])[0]
                        audio_list.append(sample / 32767.0)
                audio_data = audio_list
            
            # エンコード
            encoded_info = codec_manager.encode_audio(audio_data, args.codec, args.quality)
            
            # 結果保存
            with open(args.output, 'w') as f:
                json.dump(encoded_info, f, indent=2)
            
            print(f"✓ Encoding complete: {args.output}")
            print(f"  Original size: {encoded_info['original_size']} bytes")
            print(f"  Compressed size: {encoded_info['compressed_size']} bytes")
            print(f"  Compression ratio: {encoded_info['compression_ratio']:.1f}x")
            
        elif args.action == 'decode':
            if not args.encoded_file or not args.output:
                print("Error: --encoded-file and --output are required for decoding")
                return
            
            print(f"Decoding {args.encoded_file} to {args.output}")
            
            # エンコード済みデータ読み込み
            with open(args.encoded_file, 'r') as f:
                encoded_info = json.load(f)
            
            # デコード
            decoded_audio = codec_manager.decode_audio(encoded_info)
            
            # WAVファイル保存
            audio_array = array.array('h', [int(max(-32767, min(32767, sample * 32767))) 
                                           for sample in decoded_audio])
            
            with wave.open(args.output, 'w') as wav_file:
                wav_file.setnchannels(1)  # モノラル
                wav_file.setsampwidth(2)  # 16bit
                wav_file.setframerate(44100)
                wav_file.writeframes(audio_array.tobytes())
            
            print(f"✓ Decoding complete: {args.output}")
            print(f"  Samples: {len(decoded_audio)}")
            print(f"  Duration: {len(decoded_audio)/44100:.1f}s")
            
        elif args.action == 'compare':
            if not args.input:
                print("Error: --input is required for comparison")
                return
            
            print(f"Comparing codecs for {args.input}")
            
            # 音声ファイル読み込み
            handler = AudioFormatHandler()
            audio_data, metadata = handler.load_audio(args.input)
            
            # bytes → float変換
            if isinstance(audio_data, bytes):
                audio_list = []
                for i in range(0, len(audio_data), 2):
                    if i + 1 < len(audio_data):
                        sample = struct.unpack('<h', audio_data[i:i+2])[0]
                        audio_list.append(sample / 32767.0)
                audio_data = audio_list
            
            # コーデック比較
            comparison = codec_manager.compare_codecs(audio_data, args.quality)
            
            print(f"\n=== Codec Comparison (Quality: {args.quality}) ===")
            print(f"{'Codec':<15} {'Ratio':<8} {'Size':<10} {'SNR':<8} {'Type'}")
            print("-" * 55)
            
            for codec_name, stats in comparison.items():
                if 'error' in stats:
                    print(f"{codec_name:<15} ERROR: {stats['error']}")
                else:
                    print(f"{codec_name:<15} "
                          f"{stats['compression_ratio']:<7.1f}x "
                          f"{stats['compressed_size']:<9} "
                          f"{stats['snr_db']:<7.1f} "
                          f"{stats['codec_type']}")
            
            # 詳細結果保存
            if args.output:
                with open(args.output, 'w') as f:
                    json.dump(comparison, f, indent=2)
                print(f"\nDetailed results saved to: {args.output}")
        
        else:
            print(f"Unknown codec action: {args.action}")
            return
        
        print(f"✓ Codec processing complete")
        
    except Exception as e:
        print(f"Codec processing error: {e}")

def process_train(args):
    """Process ML training command"""
    try:
        if args.action == 'demo':
            print("🤖 Running ML training demo...")
            demo_ml_training()
            return
        
        model_manager = ModelManager(args.output_dir)
        
        if args.action == 'dataset':
            if not args.dataset_dir:
                print("Error: --dataset-dir is required for dataset action")
                return
            
            print(f"Creating dataset from directory: {args.dataset_dir}")
            
            dataset = AudioDataset()
            
            # パターンベースラベリング
            pattern_to_label = {
                'music': 'music',
                'speech': 'speech', 
                'noise': 'noise',
                'silence': 'silence',
                'tone': 'tone'
            }
            
            dataset.load_from_directory(args.dataset_dir, pattern_to_label)
            
            if args.augment:
                print("Applying data augmentation...")
                dataset.augment_dataset(augmentation_factor=2)
            
            # データセット保存
            dataset_path = os.path.join(args.output_dir, "dataset.pkl")
            dataset.save_dataset(dataset_path)
            
            print(f"✓ Dataset created: {len(dataset.samples)} samples")
            print(f"  Saved to: {dataset_path}")
            
            # ラベル分布表示
            label_counts = {}
            for label in dataset.labels:
                label_counts[label] = label_counts.get(label, 0) + 1
            
            print("Label distribution:")
            for label, count in label_counts.items():
                print(f"  {label}: {count}")
                
        elif args.action == 'train':
            if not args.model_name:
                print("Error: --model-name is required for training")
                return
            
            print(f"Training model: {args.model_name}")
            
            # データセット読み込み
            dataset_path = os.path.join(args.output_dir, "dataset.pkl")
            if not os.path.exists(dataset_path):
                print(f"Error: Dataset not found: {dataset_path}")
                print("Please create dataset first with 'train dataset' command")
                return
                
            dataset = AudioDataset()
            dataset.load_dataset(dataset_path)
            
            print(f"Loaded dataset: {len(dataset.samples)} samples")
            
            # データセット分割
            train_data, val_data, test_data = dataset.split_dataset()
            
            # モデル訓練
            model_type_map = {
                'audio_classifier': ModelType.AUDIO_CLASSIFIER,
                'emotion_detector': ModelType.EMOTION_DETECTOR
            }
            model_type = model_type_map.get(args.model_type, ModelType.AUDIO_CLASSIFIER)
            
            trainer = NeuralNetworkTrainer({
                'hidden_size': 64,
                'model_type': args.model_type
            })
            
            print(f"Training {args.model_type} for {args.epochs} epochs...")
            training_result = trainer.train_model(
                train_data, val_data, args.epochs, args.learning_rate
            )
            
            # モデル保存
            model_id = model_manager.save_model(
                training_result['model'],
                args.model_name,
                model_type,
                {
                    'accuracy': training_result['final_accuracy'],
                    'epochs': args.epochs,
                    'learning_rate': args.learning_rate,
                    'train_samples': len(train_data['samples']),
                    'val_samples': len(val_data['samples']),
                    'classes': list(training_result['label_mapping'].keys())
                }
            )
            
            print(f"✓ Training complete: {model_id}")
            print(f"  Final accuracy: {training_result['final_accuracy']:.3f}")
            
        elif args.action == 'evaluate':
            if not args.model_name:
                print("Error: --model-name is required for evaluation")
                return
            
            print(f"Evaluating model: {args.model_name}")
            
            # モデル読み込み
            model_data = model_manager.load_model(args.model_name, args.version)
            
            # テストデータでの評価
            dataset_path = os.path.join(args.output_dir, "dataset.pkl")
            if os.path.exists(dataset_path):
                dataset = AudioDataset()
                dataset.load_dataset(dataset_path)
                
                train_data, val_data, test_data = dataset.split_dataset()
                
                # 評価実行
                trainer = NeuralNetworkTrainer(model_data['model']['config'])
                trainer.model = model_data['model']
                
                test_features = [trainer.extract_features(sample) for sample in test_data['samples']]
                
                # 予測実行
                correct = 0
                total = len(test_features)
                
                for i, features in enumerate(test_features):
                    prediction = trainer.forward_pass(features)
                    predicted_class = prediction.index(max(prediction))
                    
                    # 実際のラベルインデックス
                    actual_label = test_data['labels'][i]
                    label_mapping = model_data.get('label_mapping', {})
                    actual_class = label_mapping.get(actual_label, 0)
                    
                    if predicted_class == actual_class:
                        correct += 1
                
                test_accuracy = correct / total if total > 0 else 0.0
                print(f"Test accuracy: {test_accuracy:.3f}")
            else:
                print("No test dataset available")
                
        elif args.action == 'models':
            print("Available models:")
            models = model_manager.list_models()
            
            if not models:
                print("  No models found")
            else:
                for name, versions in models.items():
                    print(f"\n{name}:")
                    for version_info in sorted(versions, key=lambda x: x['created_at'], reverse=True):
                        metadata = version_info.get('metadata', {})
                        accuracy = metadata.get('accuracy', 'N/A')
                        classes = metadata.get('classes', [])
                        
                        print(f"  {version_info['version']} - "
                              f"Accuracy: {accuracy}, "
                              f"Classes: {len(classes)}, "
                              f"Type: {version_info['type']}")
        
        else:
            print(f"Unknown training action: {args.action}")
            return
        
        print(f"✓ ML training processing complete")
        
    except Exception as e:
        print(f"ML training error: {e}")


if __name__ == '__main__':
    sys.exit(main())