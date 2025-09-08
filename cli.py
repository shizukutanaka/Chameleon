#!/usr/bin/env python3
"""
Chameleon CLI - Clean Code Principles
- Single Responsibility: CLI interface only
- Dependency Inversion: Depends on core module abstractions
- Open/Closed Principle: Easy to add new commands
"""

import sys
import argparse
import json
import os
from typing import Dict, Any, Optional, List
from pathlib import Path

try:
    from .types import AudioData, AudioConstants, get_fallback_logger
    from .core import (
        load_config, validate_audio_params, ensure_output_dir,
        generate_sine_wave, write_wav_file, get_file_size, read_wav_file,
        get_system_capabilities, normalize_audio, trim_silence, adjust_volume, 
        mix_audio, concatenate_audio, create_silence, system_health_check,
        detect_audio_properties, get_audio_summary, is_valid_audio_file
    )
    logger = get_fallback_logger('chameleon.cli')
    TYPES_AVAILABLE = True
except ImportError:
    from core import (
        load_config, validate_audio_params, ensure_output_dir,
        generate_sine_wave, write_wav_file, get_file_size, read_wav_file,
        get_system_capabilities, normalize_audio, trim_silence, adjust_volume, 
        mix_audio, concatenate_audio, create_silence, system_health_check
    )
    import logging
    logger = logging.getLogger('chameleon.cli')
    TYPES_AVAILABLE = False

# Import new modules
try:
    from audio_formats import AudioConverter, get_audio_info, get_supported_formats
    from batch_processor import BatchProcessor
    from profiles import ProfileManager, get_profile_manager, list_profiles, get_profile
    from logger import configure_logging, LogLevel
    NEW_FEATURES_AVAILABLE = True
except ImportError as e:
    print(f"Some advanced features unavailable: {e}")
    NEW_FEATURES_AVAILABLE = False

class CommandResult:
    """Unified interface for command execution results"""
    def __init__(self, success: bool, message: str = "", data: Any = None, details: str = None):
        self.success = success
        self.message = message  
        self.data = data
        self.details = details
        
    def format_output(self, verbose: bool = False) -> str:
        """Format command result for display"""
        icon = "✅" if self.success else "❌"
        output = f"{icon} {self.message}"
        
        if verbose and self.details:
            output += f"\n{self.details}"
            
        if verbose and self.data and isinstance(self.data, dict):
            # Format additional data nicely
            for key, value in self.data.items():
                if isinstance(value, (int, float)):
                    output += f"\n  {key}: {value}"
                elif isinstance(value, str) and len(value) < 100:
                    output += f"\n  {key}: {value}"
                    
        return output

class BaseCommand:
    """Base class for commands - Open/Closed Principle"""
    def __init__(self, config: Dict[str, Any]):
        self.config = config
    
    def execute(self, args: argparse.Namespace) -> CommandResult:
        raise NotImplementedError
    
    def validate_input_file(self, filepath: str) -> CommandResult:
        """Common input file validation"""
        if not filepath:
            return CommandResult(False, "No input file specified")
        
        if not os.path.exists(filepath):
            return CommandResult(False, f"File not found: {filepath}")
            
        if not is_valid_audio_file(filepath):
            return CommandResult(False, f"Invalid or unsupported audio file: {filepath}")
            
        return CommandResult(True, "File validation passed")

class ToneCommand(BaseCommand):
    """Tone generation command - Single Responsibility Principle"""
    def execute(self, args: argparse.Namespace) -> CommandResult:
        freq = getattr(args, 'freq', 440.0)
        duration = getattr(args, 'duration', 1.0)
        output = getattr(args, 'output', 'tone.wav')
        
        # Enhanced parameter validation
        if TYPES_AVAILABLE:
            if not (AudioConstants.MIN_FREQUENCY <= freq <= AudioConstants.MAX_FREQUENCY):
                return CommandResult(False, f"Frequency {freq}Hz out of range ({AudioConstants.MIN_FREQUENCY}-{AudioConstants.MAX_FREQUENCY}Hz)")
            if not (AudioConstants.MIN_DURATION <= duration <= AudioConstants.MAX_DURATION):
                return CommandResult(False, f"Duration {duration}s out of range ({AudioConstants.MIN_DURATION}-{AudioConstants.MAX_DURATION}s)")
        else:
            if not validate_audio_params(freq, duration, self.config.get('sample_rate', 44100)):
                return CommandResult(False, "Invalid parameters")
        
        if not ensure_output_dir(output):
            return CommandResult(False, f"Failed to create output directory: {os.path.dirname(output)}")
        
        try:
            sample_rate = self.config.get('audio', {}).get('sample_rate', 44100)
            audio_data = generate_sine_wave(freq, duration, sample_rate)
            
            if write_wav_file(output, audio_data):
                size = get_file_size(output)
                size_mb = size / (1024 * 1024) if size > 0 else 0
                
                details = f"Generated {duration:.2f}s sine wave at {freq:.1f}Hz"
                details += f"\nSample rate: {sample_rate}Hz"
                details += f"\nFile size: {size_mb:.2f}MB"
                
                return CommandResult(
                    True, 
                    f"Tone generated: {output}",
                    {'frequency': freq, 'duration': duration, 'file_size': size, 'sample_rate': sample_rate},
                    details
                )
            else:
                return CommandResult(False, f"Failed to write file: {output}")
                
        except Exception as e:
            logger.error(f"Tone generation failed: {e}")
            return CommandResult(False, f"Generation error: {e}")

class AnalyzeCommand(BaseCommand):
    """Audio analysis command - Single Responsibility Principle"""
    def execute(self, args: argparse.Namespace) -> CommandResult:
        input_file = getattr(args, 'input', None)
        
        # Validate input file
        validation = self.validate_input_file(input_file)
        if not validation.success:
            return validation
        
        try:
            # Get comprehensive audio properties
            properties = detect_audio_properties(input_file)
            if not properties:
                return CommandResult(False, f"Failed to analyze file: {input_file}")
            
            # Generate human-readable summary
            summary = get_audio_summary(input_file)
            
            # Create detailed analysis
            details = f"File: {os.path.basename(input_file)}"
            details += f"\nFormat: {properties.get('format', 'unknown')}"
            details += f"\nDuration: {properties.get('duration_seconds', 0):.2f}s"
            details += f"\nSample Rate: {properties.get('sample_rate', 0)}Hz"
            details += f"\nChannels: {properties.get('channels', 0)}"
            details += f"\nBit Depth: {properties.get('bit_depth', 0)}"
            details += f"\nFile Size: {properties.get('file_size_mb', 0):.2f}MB"
            details += f"\nQuality: {properties.get('estimated_quality', 'unknown')}"
            
            # Audio analysis
            if properties.get('max_amplitude_ratio', 0) > 0:
                details += f"\nPeak Level: {properties.get('max_amplitude_ratio', 0):.1%}"
                details += f"\nRMS Level: {properties.get('rms_amplitude_ratio', 0):.1%}"
                details += f"\nDynamic Range: {properties.get('dynamic_range_db', 0):.1f}dB"
            
            # Warnings
            if properties.get('is_clipped', False):
                details += "\n⚠️  Audio appears to be clipped"
            if properties.get('is_silent', False):
                details += "\n🔇 Audio is silent"
            
            return CommandResult(True, f"Analysis complete: {summary}", properties, details)
            
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            return CommandResult(False, f"Analysis error: {e}")

class StatusCommand(BaseCommand):
    """System status display command - Single Responsibility Principle"""
    def execute(self, args: argparse.Namespace) -> CommandResult:
        try:
            caps = get_system_capabilities()
            
            # Calculate system health
            available_features = sum(caps.values())
            total_features = len(caps)
            health_percentage = (available_features / total_features * 100) if total_features > 0 else 0
            
            # Determine system status
            if health_percentage >= 80:
                status_icon = "🟢"
                status_text = "Excellent"
            elif health_percentage >= 60:
                status_icon = "🟡" 
                status_text = "Good"
            elif health_percentage >= 40:
                status_icon = "🟠"
                status_text = "Limited"
            else:
                status_icon = "🔴"
                status_text = "Basic"
            
            # Build detailed status
            details = f"System Health: {status_icon} {status_text} ({health_percentage:.0f}%)"
            details += f"\nFeatures Available: {available_features}/{total_features}"
            details += "\n\nCapabilities:"
            
            for capability, available in sorted(caps.items()):
                icon = "✅" if available else "❌"
                details += f"\n  {icon} {capability.replace('_', ' ').title()}"
            
            # Configuration info
            config_path = getattr(args, 'config', 'config.yaml')
            if os.path.exists(config_path):
                details += f"\n\nConfiguration: {config_path} ✅"
            else:
                details += f"\n\nConfiguration: {config_path} (using defaults)"
            
            # Performance info
            try:
                from .perf import get_performance_stats
                perf = get_performance_stats()
                if 'memory_usage_mb' in perf:
                    details += f"\nMemory Usage: {perf['memory_usage_mb']:.1f}MB"
                if 'lut_initialized' in perf:
                    lut_status = "✅" if perf.get('sine_lut_initialized', False) else "❌"
                    details += f"\nOptimization Cache: {lut_status}"
            except ImportError:
                pass
            
            status_data = {
                'version': '2.0.0',
                'health_percentage': health_percentage,
                'available_features': available_features,
                'total_features': total_features,
                'capabilities': caps
            }
            
            return CommandResult(True, f"System Status: {status_text}", status_data, details)
            
        except Exception as e:
            logger.error(f"Status check failed: {e}")
            return CommandResult(False, f"Status check error: {e}")

class ProcessCommand(BaseCommand):
    """Audio processing command with multiple operations"""
    def execute(self, args: argparse.Namespace) -> CommandResult:
        input_file = getattr(args, 'input', None)
        output_file = getattr(args, 'output', None)
        
        # Validate input
        validation = self.validate_input_file(input_file)
        if not validation.success:
            return validation
            
        if not output_file:
            # Generate output filename
            input_path = Path(input_file)
            output_file = str(input_path.parent / f"{input_path.stem}_processed{input_path.suffix}")
        
        try:
            # Read input audio
            result = read_wav_file(input_file)
            if not result:
                return CommandResult(False, f"Failed to read input file: {input_file}")
            
            audio_data, _ = result
            processed_audio = audio_data
            operations = []
            
            # Apply requested processing operations
            if getattr(args, 'normalize', False):
                target_amp = getattr(args, 'amplitude', 0.8)
                processed_audio = normalize_audio(processed_audio, target_amp)
                if processed_audio:
                    operations.append(f"normalize (target: {target_amp})")
                else:
                    return CommandResult(False, "Normalization failed")
            
            if getattr(args, 'trim', False):
                threshold = getattr(args, 'threshold', 0.01)
                processed_audio = trim_silence(processed_audio, threshold)
                if processed_audio:
                    operations.append(f"trim silence (threshold: {threshold})")
                else:
                    return CommandResult(False, "Silence trimming failed")
                    
            if getattr(args, 'volume', None) is not None:
                volume = float(args.volume)
                processed_audio = adjust_volume(processed_audio, volume)
                if processed_audio:
                    operations.append(f"adjust volume ({volume}x)")
                else:
                    return CommandResult(False, "Volume adjustment failed")
            
            # Write output
            if not ensure_output_dir(output_file):
                return CommandResult(False, f"Failed to create output directory: {os.path.dirname(output_file)}")
            
            if write_wav_file(output_file, processed_audio):
                size = get_file_size(output_file)
                size_mb = size / (1024 * 1024) if size > 0 else 0
                
                operations_text = ", ".join(operations) if operations else "no operations"
                details = f"Input: {os.path.basename(input_file)}"
                details += f"\nOutput: {os.path.basename(output_file)}"
                details += f"\nOperations: {operations_text}"
                details += f"\nOutput size: {size_mb:.2f}MB"
                
                return CommandResult(
                    True,
                    f"Processing complete: {output_file}",
                    {'operations': operations, 'output_size': size},
                    details
                )
            else:
                return CommandResult(False, f"Failed to write output file: {output_file}")
                
        except Exception as e:
            logger.error(f"Processing failed: {e}")
            return CommandResult(False, f"Processing error: {e}")

class TestCommand(BaseCommand):
    """システムテストコマンド - 単一責任原則"""
    def execute(self, args: argparse.Namespace) -> CommandResult:
        tests = []
        
        # テスト1: 基本音声生成
        try:
            audio = generate_sine_wave(440, 0.1, self.config['sample_rate'])
            success = write_wav_file('test_tone.wav', audio)
            tests.append(('音声生成', success))
            
            if success:
                result = read_wav_file('test_tone.wav')
                tests.append(('音声読み込み', result is not None))
                
                try:
                    os.remove('test_tone.wav')
                except Exception:
                    pass
            
        except Exception:
            tests.append(('音声生成', False))
            tests.append(('音声読み込み', False))
        
        # テスト2: 設定
        tests.append(('設定読み込み', 'sample_rate' in self.config))
        
        passed = sum(1 for _, success in tests if success)
        total = len(tests)
        
        return CommandResult(
            passed == total,
            f"テスト結果: {passed}/{total}",
            {'tests': tests, 'passed': passed, 'total': total}
        )

class BatchCommand(BaseCommand):
    """バッチ処理コマンド - 単一責任原則"""
    def execute(self, args: argparse.Namespace) -> CommandResult:
        from core import batch_generate_tones, batch_analyze_directory
        
        if hasattr(args, 'frequencies') and args.frequencies:
            # バッチトーン生成
            frequencies = [float(f) for f in args.frequencies.split(',')]
            duration = getattr(args, 'duration', 1.0)
            output_dir = getattr(args, 'output_dir', './batch_output')
            
            results = batch_generate_tones(frequencies, duration, self.config['sample_rate'], output_dir)
            success_count = sum(1 for success in results.values() if success)
            
            return CommandResult(
                success_count > 0,
                f"バッチ生成完了: {success_count}/{len(results)} 成功",
                results
            )
        
        elif hasattr(args, 'directory') and args.directory:
            # ディレクトリ分析
            analysis = batch_analyze_directory(args.directory)
            
            if 'error' in analysis:
                return CommandResult(False, analysis['error'])
            
            return CommandResult(
                True,
                f"分析完了: {analysis.get('files_analyzed', 0)}ファイル",
                analysis
            )
        
        else:
            return CommandResult(False, "バッチ処理オプションが指定されていません")

class InfoCommand(BaseCommand):
    """詳細情報コマンド - 単一責任原則"""
    def execute(self, args: argparse.Namespace) -> CommandResult:
        from core import analyze_audio_file
        
        if not hasattr(args, 'file') or not args.file:
            return CommandResult(False, "ファイルが指定されていません")
        
        analysis = analyze_audio_file(args.file)
        if not analysis:
            return CommandResult(False, f"ファイル分析失敗: {args.file}")
        
        return CommandResult(True, "音声ファイル分析完了", analysis)

class ProcessCommand(BaseCommand):
    """音声処理コマンド - 単一責任原則"""
    def execute(self, args: argparse.Namespace) -> CommandResult:
        from core import (read_wav_file, write_wav_file, normalize_audio, trim_silence, 
                         adjust_volume, add_echo, fade_in_out, reverse_audio, 
                         apply_low_pass_filter, audio_statistics)
        
        if not hasattr(args, 'input') or not args.input:
            return CommandResult(False, "入力ファイルが指定されていません")
        
        # 音声ファイル読み込み
        result = read_wav_file(args.input)
        if not result:
            return CommandResult(False, f"ファイル読み込み失敗: {args.input}")
        
        audio_data, _ = result
        processed_audio = audio_data
        operations = []
        
        # 正規化処理
        if hasattr(args, 'normalize') and args.normalize:
            target_amp = getattr(args, 'amplitude', 0.8)
            normalized = normalize_audio(processed_audio, target_amp)
            if normalized:
                processed_audio = normalized
                operations.append(f"正規化(振幅:{target_amp})")
        
        # 無音トリミング
        if hasattr(args, 'trim') and args.trim:
            threshold = getattr(args, 'threshold', 0.01)
            trimmed = trim_silence(processed_audio, threshold)
            if trimmed:
                processed_audio = trimmed
                operations.append(f"無音トリミング(閾値:{threshold})")
        
        # 音量調整
        if hasattr(args, 'volume') and args.volume is not None:
            volume_factor = args.volume
            volume_adjusted = adjust_volume(processed_audio, volume_factor)
            if volume_adjusted:
                processed_audio = volume_adjusted
                operations.append(f"音量調整({volume_factor}x)")
        
        # エコー効果
        if hasattr(args, 'echo') and args.echo:
            delay = getattr(args, 'echo_delay', 0.3)
            decay = getattr(args, 'echo_decay', 0.4)
            echo_audio = add_echo(processed_audio, delay, decay)
            if echo_audio:
                processed_audio = echo_audio
                operations.append(f"エコー(遅延:{delay}s, 減衰:{decay})")
        
        # フェード効果
        if hasattr(args, 'fade') and args.fade:
            fade_in = getattr(args, 'fade_in', 0.1)
            fade_out = getattr(args, 'fade_out', 0.1)
            faded_audio = fade_in_out(processed_audio, fade_in, fade_out)
            if faded_audio:
                processed_audio = faded_audio
                operations.append(f"フェード(イン:{fade_in}s, アウト:{fade_out}s)")
        
        # 逆再生
        if hasattr(args, 'reverse') and args.reverse:
            reversed_audio = reverse_audio(processed_audio)
            if reversed_audio:
                processed_audio = reversed_audio
                operations.append("逆再生")
        
        # ローパスフィルター
        if hasattr(args, 'lowpass') and args.lowpass is not None:
            cutoff = args.lowpass
            filtered_audio = apply_low_pass_filter(processed_audio, cutoff)
            if filtered_audio:
                processed_audio = filtered_audio
                operations.append(f"ローパスフィルター(カットオフ:{cutoff})")
        
        # 統計情報の表示
        if hasattr(args, 'stats') and args.stats:
            stats = audio_statistics(processed_audio)
            if stats:
                operations.append("統計情報取得")
        
        # 出力ファイル名決定
        output_file = getattr(args, 'output', None)
        if not output_file:
            # デフォルトの出力ファイル名生成
            import os
            base, ext = os.path.splitext(args.input)
            output_file = f"{base}_processed{ext}"
        
        # 処理結果を保存
        if write_wav_file(output_file, processed_audio):
            message = f"処理完了: {args.input} -> {output_file}"
            if operations:
                message += f" ({', '.join(operations)})"
            
            # 統計情報を追加で返す
            result_data = None
            if hasattr(args, 'stats') and args.stats and 'stats' in locals():
                result_data = stats
                
            return CommandResult(True, message, result_data)
        else:
            return CommandResult(False, f"出力失敗: {output_file}")

class EffectsCommand(BaseCommand):
    """高度な音声効果コマンド - 単一責任原則"""
    def execute(self, args: argparse.Namespace) -> CommandResult:
        from core import (generate_chord, mix_audio, read_wav_file, write_wav_file,
                         concatenate_audio, create_silence, audio_statistics)
        
        # 和音生成
        if hasattr(args, 'chord') and args.chord:
            frequencies = [float(f) for f in args.chord.split(',')]
            duration = getattr(args, 'duration', 1.0)
            output_file = getattr(args, 'output', 'chord.wav')
            
            chord_audio = generate_chord(frequencies, duration, self.config['sample_rate'])
            if chord_audio and write_wav_file(output_file, chord_audio):
                return CommandResult(True, f"和音生成完了: {output_file} ({frequencies}Hz)")
            else:
                return CommandResult(False, "和音生成に失敗しました")
        
        # ミキシング
        if hasattr(args, 'mix') and args.mix:
            files = args.mix.split(',')
            if len(files) < 2:
                return CommandResult(False, "ミキシングには2つ以上のファイルが必要です")
            
            audio_list = []
            for file in files:
                result = read_wav_file(file.strip())
                if result:
                    audio_data, _ = result
                    audio_list.append(audio_data)
            
            if len(audio_list) < 2:
                return CommandResult(False, "有効な音声ファイルが2つ未満です")
            
            # 最初の2つをミキシングし、残りを順次追加
            mixed_audio = mix_audio(audio_list[0], audio_list[1], 0.5)
            for i in range(2, len(audio_list)):
                if mixed_audio:
                    mixed_audio = mix_audio(mixed_audio, audio_list[i], 0.5)
            
            output_file = getattr(args, 'output', 'mixed.wav')
            if mixed_audio and write_wav_file(output_file, mixed_audio):
                return CommandResult(True, f"ミキシング完了: {output_file}")
            else:
                return CommandResult(False, "ミキシングに失敗しました")
        
        # 連結
        if hasattr(args, 'concat') and args.concat:
            files = args.concat.split(',')
            audio_list = []
            
            for file in files:
                file = file.strip()
                result = read_wav_file(file)
                if result:
                    audio_data, _ = result
                    audio_list.append(audio_data)
                else:
                    return CommandResult(False, f"ファイル読み込み失敗: {file}")
            
            concatenated = concatenate_audio(*audio_list)
            output_file = getattr(args, 'output', 'concatenated.wav')
            
            if concatenated and write_wav_file(output_file, concatenated):
                return CommandResult(True, f"連結完了: {output_file} ({len(audio_list)}ファイル)")
            else:
                return CommandResult(False, "連結に失敗しました")
        
        # 無音生成
        if hasattr(args, 'silence') and args.silence:
            duration = args.silence
            output_file = getattr(args, 'output', 'silence.wav')
            
            silence_audio = create_silence(duration, self.config['sample_rate'])
            if write_wav_file(output_file, silence_audio):
                return CommandResult(True, f"無音生成完了: {output_file} ({duration}秒)")
            else:
                return CommandResult(False, "無音生成に失敗しました")
        
        # 統計表示
        if hasattr(args, 'analyze') and args.analyze:
            result = read_wav_file(args.analyze)
            if not result:
                return CommandResult(False, f"ファイル読み込み失敗: {args.analyze}")
            
            audio_data, _ = result
            stats = audio_statistics(audio_data)
            
            if stats:
                return CommandResult(True, f"音声統計完了: {args.analyze}", stats)
            else:
                return CommandResult(False, "統計取得に失敗しました")
        
        return CommandResult(False, "有効なエフェクトオプションが指定されていません")

class DiagnosticsCommand(BaseCommand):
    """システム診断コマンド - 統合診断機能"""
    def execute(self, args: argparse.Namespace) -> CommandResult:
        from core import system_health_check, security_audit, resource_monitor
        from perf import get_performance_stats, benchmark_audio_generation, optimize_system, advanced_system_benchmark
        
        diag_type = getattr(args, 'type', 'health')
        
        if diag_type == 'health':
            # システム健全性チェック
            health = system_health_check()
            return CommandResult(health['overall'], "システム健全性チェック完了", health)
            
        elif diag_type == 'security':
            # セキュリティ監査
            audit = security_audit()
            return CommandResult(
                audit.get('security_level') in ['excellent', 'good'], 
                f"セキュリティ監査完了 - レベル: {audit.get('security_level', 'unknown')}", 
                audit
            )
            
        elif diag_type == 'performance':
            # パフォーマンス統計
            stats = get_performance_stats()
            return CommandResult(True, "パフォーマンス統計取得完了", stats)
            
        elif diag_type == 'benchmark':
            # ベンチマーク実行
            iterations = getattr(args, 'iterations', 25)
            results = benchmark_audio_generation(iterations)
            return CommandResult(True, f"ベンチマーク完了 ({iterations}回)", results)
            
        elif diag_type == 'optimize':
            # システム最適化
            results = optimize_system()
            return CommandResult(True, "システム最適化完了", results)
            
        elif diag_type == 'comprehensive':
            # 総合ベンチマーク
            results = advanced_system_benchmark()
            score = results.get('overall_performance_score', 0)
            return CommandResult(True, f"総合ベンチマーク完了 - スコア: {score:.1f}", results)
            
        else:
            return CommandResult(False, f"不明な診断タイプ: {diag_type}")

class ConvertCommand(BaseCommand):
    """Audio format conversion command"""
    def execute(self, args: argparse.Namespace) -> CommandResult:
        if not NEW_FEATURES_AVAILABLE:
            return CommandResult(False, "Conversion features not available")
        
        input_file = getattr(args, 'input', None)
        output_file = getattr(args, 'output', None)
        target_format = getattr(args, 'format', None)
        quality = getattr(args, 'quality', 'high')
        
        if not input_file:
            return CommandResult(False, "Input file not specified")
        
        if not output_file:
            from pathlib import Path
            input_path = Path(input_file)
            if target_format:
                output_file = f"{input_path.stem}.{target_format}"
            else:
                return CommandResult(False, "Output file or format must be specified")
        
        converter = AudioConverter()
        success = converter.convert_file(input_file, output_file, target_format, quality)
        
        if success:
            return CommandResult(True, f"Converted: {input_file} -> {output_file}")
        else:
            return CommandResult(False, f"Conversion failed: {input_file}")

class ProfileCommand(BaseCommand):
    """Profile management command"""
    def execute(self, args: argparse.Namespace) -> CommandResult:
        if not NEW_FEATURES_AVAILABLE:
            return CommandResult(False, "Profile features not available")
        
        manager = get_profile_manager()
        operation = getattr(args, 'profile_operation', 'list')
        
        if operation == 'list':
            profiles = list_profiles()
            active = manager.get_active_profile()
            active_name = active.name if active else "None"
            
            return CommandResult(True, f"Available profiles: {', '.join(profiles)}\nActive: {active_name}", profiles)
        
        elif operation == 'show':
            name = getattr(args, 'name', None)
            if not name:
                return CommandResult(False, "Profile name not specified")
            
            info = manager.get_profile_info(name)
            if info:
                return CommandResult(True, f"Profile info: {name}", info)
            else:
                return CommandResult(False, f"Profile not found: {name}")
        
        elif operation == 'set':
            name = getattr(args, 'name', None)
            if not name:
                return CommandResult(False, "Profile name not specified")
            
            success = manager.set_active_profile(name)
            if success:
                return CommandResult(True, f"Active profile set to: {name}")
            else:
                return CommandResult(False, f"Failed to set profile: {name}")
        
        elif operation == 'create':
            name = getattr(args, 'name', None)
            description = getattr(args, 'description', 'Custom profile')
            template = getattr(args, 'template', 'podcast')
            
            if not name:
                return CommandResult(False, "Profile name not specified")
            
            profile = manager.create_profile_from_template(name, description, template)
            if profile and manager.save_profile(profile):
                return CommandResult(True, f"Profile created: {name}")
            else:
                return CommandResult(False, f"Failed to create profile: {name}")
        
        else:
            return CommandResult(False, f"Unknown profile operation: {operation}")

class BatchConvertCommand(BaseCommand):
    """Batch file conversion command"""
    def execute(self, args: argparse.Namespace) -> CommandResult:
        if not NEW_FEATURES_AVAILABLE:
            return CommandResult(False, "Batch conversion features not available")
        
        input_files = getattr(args, 'files', [])
        output_dir = getattr(args, 'output_dir', './converted')
        target_format = getattr(args, 'format', 'wav')
        quality = getattr(args, 'quality', 'high')
        workers = getattr(args, 'workers', None)
        
        if not input_files:
            return CommandResult(False, "No input files specified")
        
        # Expand wildcards if any
        import glob
        expanded_files = []
        for file_pattern in input_files:
            expanded_files.extend(glob.glob(file_pattern))
        
        if not expanded_files:
            return CommandResult(False, "No files found matching the patterns")
        
        processor = BatchProcessor(max_workers=workers)
        result = processor.batch_convert_files(expanded_files, output_dir, target_format, quality)
        
        if 'error' in result:
            return CommandResult(False, result['error'])
        
        message = f"Batch conversion completed: {result['successful']}/{result['total_files']} files"
        return CommandResult(True, message, result)

class AdvancedBatchCommand(BaseCommand):
    """Advanced batch processing command"""  
    def execute(self, args: argparse.Namespace) -> CommandResult:
        if not NEW_FEATURES_AVAILABLE:
            return CommandResult(False, "Advanced batch features not available")
        
        operation = getattr(args, 'batch_operation', 'tones')
        
        if operation == 'tones':
            return self._batch_tones(args)
        elif operation == 'analyze':
            return self._batch_analyze(args)
        else:
            return CommandResult(False, f"Unknown batch operation: {operation}")
    
    def _batch_tones(self, args) -> CommandResult:
        frequencies_str = getattr(args, 'frequencies', '440,880,1320')
        duration = getattr(args, 'duration', 1.0)
        output_dir = getattr(args, 'output_dir', './batch_tones')
        workers = getattr(args, 'workers', None)
        
        try:
            frequencies = [float(f.strip()) for f in frequencies_str.split(',')]
        except ValueError:
            return CommandResult(False, "Invalid frequency format")
        
        from batch_processor import batch_generate_tones
        result = batch_generate_tones(frequencies, duration, 44100, output_dir, workers)
        
        if 'error' in result:
            return CommandResult(False, result['error'])
        
        message = f"Generated {result['successful']}/{result['total_files']} tone files"
        return CommandResult(True, message, result)
    
    def _batch_analyze(self, args) -> CommandResult:
        input_files = getattr(args, 'files', [])
        workers = getattr(args, 'workers', None)
        
        if not input_files:
            return CommandResult(False, "No input files specified")
        
        # Expand wildcards
        import glob
        expanded_files = []
        for file_pattern in input_files:
            expanded_files.extend(glob.glob(file_pattern))
        
        if not expanded_files:
            return CommandResult(False, "No files found")
        
        from batch_processor import batch_analyze_files
        result = batch_analyze_files(expanded_files, workers)
        
        if 'error' in result:
            return CommandResult(False, result['error'])
        
        message = f"Analyzed {result['analyzed']}/{result['total_files']} files"
        return CommandResult(True, message, result)

class CommandRegistry:
    """Command registry management"""
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.commands: Dict[str, BaseCommand] = {
            'tone': ToneCommand(config),
            'analyze': AnalyzeCommand(config), 
            'status': StatusCommand(config),
            'test': TestCommand(config),
            'batch': BatchCommand(config),
            'info': InfoCommand(config),
            'process': ProcessCommand(config),
            'effects': EffectsCommand(config),
            'diagnostics': DiagnosticsCommand(config),
        }
        
        # Add new commands if features are available
        if NEW_FEATURES_AVAILABLE:
            self.commands.update({
                'convert': ConvertCommand(config),
                'profile': ProfileCommand(config),
                'batch-convert': BatchConvertCommand(config),
                'advanced-batch': AdvancedBatchCommand(config),
            })
    
    def get_command(self, name: str) -> Optional[BaseCommand]:
        return self.commands.get(name)
    
    def list_commands(self) -> List[str]:
        return list(self.commands.keys())

class OutputFormatter:
    """出力フォーマット - 単一責任原則"""
    @staticmethod
    def format_status(data: Dict[str, Any]) -> str:
        caps = data['capabilities']
        lines = [
            "=" * 50,
            f"Chameleon Voice Changer v{data['version']}",
            "=" * 50,
            "",
            "📊 システム情報:",
            f"  サンプルレート: {data['config']['sample_rate']}Hz",
            f"  チャンネル: {data['config']['channels']}",
            "",
            "🔧 利用可能機能:",
        ]
        
        for feature, available in caps.items():
            status = "✅" if available else "❌"
            lines.append(f"  {status} {feature}")
        
        lines.extend([
            "",
            f"📈 機能サマリ: {data['available_features']}/{data['total_features']} 利用可能"
        ])
        
        return "\n".join(lines)
    
    @staticmethod
    def format_test_result(data: Dict[str, Any]) -> str:
        lines = ["🧪 システムテスト結果:", ""]
        
        for i, (name, success) in enumerate(data['tests'], 1):
            status = "✅" if success else "❌"
            lines.append(f"  {i}. {name}: {status}")
        
        lines.extend([
            "",
            f"📈 テスト結果: {data['passed']}/{data['total']} 成功"
        ])
        
        return "\n".join(lines)

def create_parser() -> argparse.ArgumentParser:
    """引数パーサー作成 - 設定の一元化"""
    parser = argparse.ArgumentParser(
        prog='chameleon',
        description='Chameleon Voice Changer - Clean Architecture',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest='command', help='コマンド')
    
    # tone
    tone_parser = subparsers.add_parser('tone', help='テストトーン生成')
    tone_parser.add_argument('-f', '--freq', type=float, default=440, help='周波数 (20-20000)')
    tone_parser.add_argument('-d', '--duration', type=float, default=1.0, help='長さ (0.01-60)')
    tone_parser.add_argument('-o', '--output', default='tone.wav', help='出力ファイル')
    
    # analyze
    analyze_parser = subparsers.add_parser('analyze', help='音声解析')
    analyze_parser.add_argument('input', help='入力ファイル')
    
    # status
    subparsers.add_parser('status', help='システム状態')
    
    # test
    subparsers.add_parser('test', help='システムテスト')
    
    # batch
    batch_parser = subparsers.add_parser('batch', help='バッチ処理')
    batch_group = batch_parser.add_mutually_exclusive_group(required=True)
    batch_group.add_argument('--frequencies', help='カンマ区切りの周波数リスト (例: 440,880,1320)')
    batch_group.add_argument('--directory', help='分析するディレクトリ')
    batch_parser.add_argument('-d', '--duration', type=float, default=1.0, help='トーン長さ')
    batch_parser.add_argument('-o', '--output-dir', default='./batch_output', help='出力ディレクトリ')
    
    # info
    info_parser = subparsers.add_parser('info', help='音声ファイル詳細分析')
    info_parser.add_argument('file', help='分析する音声ファイル')
    
    # process
    process_parser = subparsers.add_parser('process', help='音声処理')
    process_parser.add_argument('input', help='入力音声ファイル')
    process_parser.add_argument('-o', '--output', help='出力ファイル名')
    process_parser.add_argument('--normalize', action='store_true', help='音量正規化を実行')
    process_parser.add_argument('--amplitude', type=float, default=0.8, help='正規化時の目標振幅 (0.1-1.0)')
    process_parser.add_argument('--trim', action='store_true', help='無音部分をトリミング')
    process_parser.add_argument('--threshold', type=float, default=0.01, help='トリミング閾値 (0.001-0.1)')
    process_parser.add_argument('--volume', type=float, help='音量調整倍率 (例: 0.5で半分、2.0で2倍)')
    process_parser.add_argument('--echo', action='store_true', help='エコー効果を追加')
    process_parser.add_argument('--echo-delay', type=float, default=0.3, help='エコー遅延時間(秒)')
    process_parser.add_argument('--echo-decay', type=float, default=0.4, help='エコー減衰率')
    process_parser.add_argument('--fade', action='store_true', help='フェードイン・アウト効果')
    process_parser.add_argument('--fade-in', type=float, default=0.1, help='フェードイン時間(秒)')
    process_parser.add_argument('--fade-out', type=float, default=0.1, help='フェードアウト時間(秒)')
    process_parser.add_argument('--reverse', action='store_true', help='逆再生')
    process_parser.add_argument('--lowpass', type=float, help='ローパスフィルタのカットオフ比率 (0.1-0.9)')
    process_parser.add_argument('--stats', action='store_true', help='音声統計情報を表示')
    
    # effects
    effects_parser = subparsers.add_parser('effects', help='高度な音声効果')
    effects_group = effects_parser.add_mutually_exclusive_group(required=True)
    effects_group.add_argument('--chord', help='和音生成 (カンマ区切り周波数リスト, 例: 261,329,392)')
    effects_group.add_argument('--mix', help='複数音声ファイルをミキシング (カンマ区切りファイルリスト)')
    effects_group.add_argument('--concat', help='複数音声ファイルを連結 (カンマ区切りファイルリスト)')
    effects_group.add_argument('--silence', type=float, help='指定時間の無音を生成(秒)')
    effects_group.add_argument('--analyze', help='音声ファイルの詳細統計を表示')
    effects_parser.add_argument('-o', '--output', help='出力ファイル名')
    effects_parser.add_argument('-d', '--duration', type=float, default=1.0, help='和音の長さ(秒)')
    
    # diagnostics
    diag_parser = subparsers.add_parser('diagnostics', help='システム診断・最適化')
    diag_parser.add_argument('type', choices=['health', 'security', 'performance', 'benchmark', 'optimize', 'comprehensive'], 
                           help='診断タイプ')
    diag_parser.add_argument('--iterations', type=int, default=25, help='ベンチマーク反復回数')
    
    # Add new command parsers if features are available
    if NEW_FEATURES_AVAILABLE:
        # convert
        convert_parser = subparsers.add_parser('convert', help='Convert audio file format')
        convert_parser.add_argument('input', help='Input audio file')
        convert_parser.add_argument('-o', '--output', help='Output file path')
        convert_parser.add_argument('-f', '--format', choices=['wav', 'mp3', 'flac', 'ogg', 'aac', 'm4a'], help='Target format')
        convert_parser.add_argument('-q', '--quality', choices=['low', 'medium', 'high'], default='high', help='Conversion quality')
        
        # profile
        profile_parser = subparsers.add_parser('profile', help='Manage configuration profiles')
        profile_subparsers = profile_parser.add_subparsers(dest='profile_operation', help='Profile operations')
        
        # profile list
        profile_subparsers.add_parser('list', help='List available profiles')
        
        # profile show
        show_parser = profile_subparsers.add_parser('show', help='Show profile details')
        show_parser.add_argument('name', help='Profile name')
        
        # profile set
        set_parser = profile_subparsers.add_parser('set', help='Set active profile')
        set_parser.add_argument('name', help='Profile name')
        
        # profile create
        create_parser = profile_subparsers.add_parser('create', help='Create new profile')
        create_parser.add_argument('name', help='Profile name')
        create_parser.add_argument('-d', '--description', default='Custom profile', help='Profile description')
        create_parser.add_argument('-t', '--template', default='podcast', help='Base template profile')
        
        # batch-convert
        batch_convert_parser = subparsers.add_parser('batch-convert', help='Convert multiple files')
        batch_convert_parser.add_argument('files', nargs='+', help='Input files (supports wildcards)')
        batch_convert_parser.add_argument('-o', '--output-dir', default='./converted', help='Output directory')
        batch_convert_parser.add_argument('-f', '--format', required=True, choices=['wav', 'mp3', 'flac', 'ogg', 'aac', 'm4a'], help='Target format')
        batch_convert_parser.add_argument('-q', '--quality', choices=['low', 'medium', 'high'], default='high', help='Conversion quality')
        batch_convert_parser.add_argument('-w', '--workers', type=int, help='Number of parallel workers')
        
        # advanced-batch
        advanced_batch_parser = subparsers.add_parser('advanced-batch', help='Advanced batch operations')
        batch_subparsers = advanced_batch_parser.add_subparsers(dest='batch_operation', help='Batch operations')
        
        # advanced-batch tones
        tones_parser = batch_subparsers.add_parser('tones', help='Generate multiple tone files')
        tones_parser.add_argument('-f', '--frequencies', default='440,880,1320', help='Comma-separated frequencies')
        tones_parser.add_argument('-d', '--duration', type=float, default=1.0, help='Duration in seconds')
        tones_parser.add_argument('-o', '--output-dir', default='./batch_tones', help='Output directory')
        tones_parser.add_argument('-w', '--workers', type=int, help='Number of parallel workers')
        
        # advanced-batch analyze
        analyze_parser = batch_subparsers.add_parser('analyze', help='Analyze multiple audio files')
        analyze_parser.add_argument('files', nargs='+', help='Input files (supports wildcards)')
        analyze_parser.add_argument('-w', '--workers', type=int, help='Number of parallel workers')
    
    return parser

def main() -> int:
    """メインエントリーポイント - 依存性逆転の実装"""
    try:
        # 設定読み込み（Pure function）
        config = load_config()
        
        # コマンドレジストリ初期化
        registry = CommandRegistry(config)
        
        # 引数解析
        parser = create_parser()
        args = parser.parse_args()
        
        # デフォルトコマンド
        command_name = args.command or 'status'
        
        # コマンド実行
        command = registry.get_command(command_name)
        if not command:
            print(f"❌ 不明なコマンド: {command_name}")
            return 1
        
        result = command.execute(args)
        
        # 出力フォーマット
        if command_name == 'status' and result.data:
            print(OutputFormatter.format_status(result.data))
        elif command_name == 'test' and result.data:
            print(OutputFormatter.format_test_result(result.data))
        elif command_name in ['analyze', 'info'] and result.data:
            print(json.dumps(result.data, indent=2, ensure_ascii=False))
        elif command_name == 'process' and result.data:
            # 処理コマンドの統計情報表示
            print(result.message)
            print("\n📊 音声統計情報:")
            for key, value in result.data.items():
                if isinstance(value, float):
                    print(f"  {key}: {value:.4f}")
                else:
                    print(f"  {key}: {value}")
        elif command_name == 'effects' and result.data:
            # エフェクトコマンドの統計情報表示
            print(result.message)
            if isinstance(result.data, dict):
                print("\n📊 音声統計情報:")
                for key, value in result.data.items():
                    if isinstance(value, float):
                        print(f"  {key}: {value:.4f}")
                    else:
                        print(f"  {key}: {value}")
        elif command_name == 'diagnostics' and result.data:
            # 診断コマンドの結果表示
            print(result.message)
            data = result.data
            
            if 'security_level' in data:
                # セキュリティ監査結果
                level_icons = {'excellent': '🟢', 'good': '🟡', 'warning': '🟠', 'critical': '🔴', 'error': '💥'}
                level = data.get('security_level', 'unknown')
                print(f"\n{level_icons.get(level, '❓')} セキュリティレベル: {level.upper()}")
                
                if data.get('issues'):
                    print("\n⚠️ 検出された問題:")
                    for i, issue in enumerate(data['issues'], 1):
                        print(f"  {i}. {issue}")
                
                if data.get('recommendations'):
                    print("\n💡 推奨事項:")
                    for i, rec in enumerate(data['recommendations'], 1):
                        print(f"  {i}. {rec}")
                        
            elif 'overall' in data:
                # 健全性チェック結果
                status_icon = "✅" if data['overall'] else "❌"
                print(f"\n{status_icon} システム総合状態: {'正常' if data['overall'] else '注意が必要'}")
                
                if data.get('warnings'):
                    print("\n⚠️ 警告:")
                    for warning in data['warnings']:
                        print(f"  • {warning}")
                        
                if data.get('errors'):
                    print("\n🚨 エラー:")
                    for error in data['errors']:
                        print(f"  • {error}")
                        
            elif 'overall_performance_score' in data:
                # 総合ベンチマーク結果
                score = data['overall_performance_score']
                print(f"\n🏆 総合スコア: {score:.1f}")
                
                if data.get('optimization_recommendations'):
                    print("\n💡 最適化推奨:")
                    for i, rec in enumerate(data['optimization_recommendations'][:3], 1):
                        print(f"  {i}. {rec}")
                        
            elif 'lut_speedup' in data:
                # ベンチマーク結果
                print(f"\n🚀 パフォーマンス結果:")
                print(f"  標準生成: {data.get('standard_total_ms', 0):.1f}ms")
                print(f"  LUT生成: {data.get('lut_total_ms', 0):.1f}ms")
                print(f"  高速化倍率: {data.get('lut_speedup', 0):.2f}x")
                
            elif 'memory_usage' in data:
                # パフォーマンス統計結果
                memory = data['memory_usage']
                print(f"\n📊 システム統計:")
                print(f"  メモリ使用量: {memory.get('rss_mb', 0):.1f}MB ({memory.get('percent', 0):.1f}%)")
                print(f"  キャッシュサイズ: {data.get('cache_size', 0)}")
                print(f"  高速ジェネレータ: {'✅' if data.get('fast_generator_ready') else '❌'}")
        elif command_name == 'batch' and result.data:
            if isinstance(result.data, dict) and 'files' in result.data:
                # ディレクトリ分析結果
                print(f"📁 分析結果: {result.data['files_analyzed']}ファイル")
                print(f"📊 合計時間: {result.data['total_duration_formatted']}")
                print(f"💾 合計サイズ: {result.data['total_size_mb']}MB")
                print(f"⏱️ 平均時間: {result.data['average_duration']}秒")
            else:
                # バッチ生成結果
                print("🎵 バッチ生成結果:")
                for freq, success in result.data.items():
                    status = "✅" if success else "❌"
                    print(f"  {status} {freq}")
        else:
            print(result.message)
        
        return 0 if result.success else 1
        
    except KeyboardInterrupt:
        print("\n⏹️ 中断されました")
        return 130
    except Exception as e:
        print(f"💥 予期しないエラー: {e}")
        return 1

if __name__ == '__main__':
    sys.exit(main())