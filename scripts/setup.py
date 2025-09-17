#!/usr/bin/env python3
"""
Automated setup and verification script for Chameleon Audio System
"""

import sys
import os
import subprocess
import platform
from pathlib import Path
import json

class SetupManager:
    def __init__(self):
        self.python_version = sys.version_info
        self.platform = platform.system()
        self.errors = []
        self.warnings = []

    def check_python_version(self):
        """Check Python version compatibility"""
        print("Checking Python version...", end='')
        if self.python_version < (3, 7):
            self.errors.append(f"Python 3.7+ required, found {sys.version}")
            print(" ❌")
            return False
        print(f" ✓ (Python {self.python_version.major}.{self.python_version.minor})")
        return True

    def check_core_modules(self):
        """Check required standard library modules"""
        print("\nChecking core modules:")
        required_modules = [
            'array', 'wave', 'math', 'json', 'pathlib',
            'os', 'sys', 'time', 'multiprocessing', 'tempfile'
        ]

        all_present = True
        for module in required_modules:
            print(f"  {module}...", end='')
            try:
                __import__(module)
                print(" ✓")
            except ImportError:
                print(" ❌")
                self.errors.append(f"Missing core module: {module}")
                all_present = False

        return all_present

    def check_optional_dependencies(self):
        """Check optional dependencies"""
        print("\nChecking optional dependencies:")
        optional = {
            'numpy': 'Optimized array operations',
            'psutil': 'System monitoring',
            'pyyaml': 'YAML configuration support'
        }

        for module, description in optional.items():
            print(f"  {module} ({description})...", end='')
            try:
                __import__(module)
                print(" ✓")
            except ImportError:
                print(" ⚠ (optional)")
                self.warnings.append(f"Optional: {module} - {description}")

    def verify_project_structure(self):
        """Verify project directory structure"""
        print("\nVerifying project structure:")
        directories = ['examples', 'scripts', 'tests', 'docs']
        files = ['chameleon.py', 'audio_effects.py', 'audio_analyzer.py']

        all_present = True
        for directory in directories:
            print(f"  Directory: {directory}/...", end='')
            if Path(directory).exists():
                print(" ✓")
            else:
                print(" Creating...")
                Path(directory).mkdir(exist_ok=True)
                print(f"  Directory: {directory}/... ✓")

        for file in files:
            print(f"  File: {file}...", end='')
            if Path(file).exists():
                print(" ✓")
            else:
                print(" ❌")
                self.errors.append(f"Missing file: {file}")
                all_present = False

        return all_present

    def create_test_audio(self):
        """Create test audio file"""
        print("\nCreating test audio file...", end='')
        try:
            import array
            import wave
            import math

            samples = array.array('h')
            sample_rate = 44100
            duration = 2.0

            for i in range(int(sample_rate * duration)):
                t = i / sample_rate
                # Create a sweep from 220Hz to 880Hz
                freq = 220 * (2 ** (2 * t / duration))
                sample = int(16000 * math.sin(2 * math.pi * freq * t))
                samples.append(sample)

            with wave.open('test_audio.wav', 'wb') as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(sample_rate)
                w.writeframes(samples.tobytes())

            print(" ✓ (test_audio.wav created)")
            return True
        except Exception as e:
            print(f" ❌ ({e})")
            self.errors.append(f"Failed to create test audio: {e}")
            return False

    def run_basic_test(self):
        """Run basic functionality test"""
        print("\nTesting basic functionality:")
        try:
            # Test import
            print("  Importing main module...", end='')
            from chameleon import AudioProcessor
            print(" ✓")

            # Test processing
            print("  Testing audio processing...", end='')
            processor = AudioProcessor()
            samples, info = processor.load_wav('test_audio.wav')
            normalized = processor.normalize(samples)
            processor.save_wav('test_output.wav', normalized, info['sample_rate'])
            print(" ✓")

            # Clean up
            Path('test_output.wav').unlink(missing_ok=True)
            return True

        except Exception as e:
            print(f" ❌ ({e})")
            self.errors.append(f"Functionality test failed: {e}")
            return False

    def install_optional_deps(self):
        """Offer to install optional dependencies"""
        if self.warnings:
            print("\nOptional dependencies not installed:")
            for warning in self.warnings:
                print(f"  - {warning}")

            response = input("\nInstall optional dependencies? (y/n): ").lower()
            if response == 'y':
                print("\nInstalling optional dependencies...")
                try:
                    subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'],
                                 check=True)
                    print("✓ Optional dependencies installed")
                except subprocess.CalledProcessError as e:
                    print(f"❌ Installation failed: {e}")
                    self.warnings.append("Failed to install optional dependencies")

    def generate_config(self):
        """Generate default configuration file"""
        print("\nGenerating default configuration...", end='')
        config = {
            "audio": {
                "default_sample_rate": 44100,
                "default_channels": 1,
                "default_bit_depth": 16
            },
            "processing": {
                "normalize_peak": 0.95,
                "silence_threshold_db": -40,
                "default_fade_ms": 100
            },
            "batch": {
                "parallel": True,
                "num_workers": 4,
                "output_format": "wav"
            },
            "performance": {
                "use_numpy": True,
                "buffer_size": 1024,
                "enable_cache": True
            }
        }

        with open('config.json', 'w') as f:
            json.dump(config, f, indent=2)

        print(" ✓ (config.json created)")

    def print_summary(self):
        """Print setup summary"""
        print("\n" + "="*60)
        print("SETUP SUMMARY")
        print("="*60)

        if self.errors:
            print("\n❌ Errors found:")
            for error in self.errors:
                print(f"  - {error}")
            print("\nPlease fix these errors before using the system.")
        else:
            print("\n✓ Setup completed successfully!")
            print("\nYou can now use Chameleon Audio System:")
            print("  python3 chameleon.py --help")
            print("\nQuick test:")
            print("  python3 chameleon.py process test_audio.wav -o output.wav --operation normalize")
            print("\nRun examples:")
            print("  python3 examples/basic_usage.py")
            print("\nRun tests:")
            print("  python3 tests/test_audio.py")

        if self.warnings:
            print("\n⚠ Warnings:")
            for warning in self.warnings:
                print(f"  - {warning}")

    def run(self):
        """Run complete setup process"""
        print("="*60)
        print("CHAMELEON AUDIO SYSTEM - SETUP")
        print("="*60)

        # Run checks
        checks = [
            self.check_python_version(),
            self.check_core_modules(),
            self.verify_project_structure()
        ]

        self.check_optional_dependencies()

        if all(checks):
            self.create_test_audio()
            self.run_basic_test()
            self.generate_config()

        # Offer to install optional deps
        if not self.errors:
            self.install_optional_deps()

        self.print_summary()

        return len(self.errors) == 0

def main():
    setup = SetupManager()
    success = setup.run()
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()