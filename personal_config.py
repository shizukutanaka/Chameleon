#!/usr/bin/env python3
"""
Personal Use Configuration - Optimized for Individual Users
Simplified setup with maximum security and features
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger("chameleon.personal")


@dataclass
class PersonalConfig:
    """Simplified configuration for personal use"""

    # Directories
    audio_library: str = str(Path.home() / "Music" / "Chameleon")
    output_directory: str = str(Path.home() / "Music" / "Chameleon" / "processed")
    temp_directory: str = str(Path.home() / ".chameleon" / "temp")

    # Security (simplified but secure)
    auto_backup: bool = True
    backup_directory: str = str(Path.home() / "Music" / "Chameleon" / "backups")
    encrypt_sensitive: bool = False  # Optional for personal use

    # Performance (optimized for personal PC)
    max_workers: int = 0  # Auto-detect CPU cores
    chunk_size: int = 131072  # 128KB
    performance_mode: str = "balanced"  # fast, balanced, safe

    # Features
    auto_analyze: bool = True  # Auto-analyze new files
    auto_normalize: bool = False  # Don't auto-normalize by default
    create_previews: bool = True  # Generate waveform previews

    # UI Preferences
    show_progress: bool = True
    color_output: bool = True
    detailed_errors: bool = True

    # File Handling
    preserve_originals: bool = True
    auto_organize: bool = True  # Organize by date/artist
    supported_formats: list = None  # Will default to ['.wav', '.wave']

    # Quick Actions
    favorite_operations: list = None  # User's most used operations

    def __post_init__(self):
        if self.supported_formats is None:
            self.supported_formats = ['.wav', '.wave']
        if self.favorite_operations is None:
            self.favorite_operations = ['normalize', 'analyze', 'denoise']

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> 'PersonalConfig':
        """Load personal configuration"""
        if config_path is None:
            config_path = Path.home() / ".chameleon" / "personal_config.json"

        if config_path.exists():
            with open(config_path, 'r') as f:
                data = json.load(f)
                return cls(**data)

        # Create default config
        config = cls()
        config.save(config_path)
        return config

    def save(self, config_path: Optional[Path] = None) -> None:
        """Save personal configuration"""
        if config_path is None:
            config_path = Path.home() / ".chameleon" / "personal_config.json"

        config_path.parent.mkdir(parents=True, exist_ok=True)

        with open(config_path, 'w') as f:
            json.dump(asdict(self), f, indent=2)

        logger.info(f"Configuration saved to {config_path}")


class PersonalSetup:
    """Easy setup wizard for personal use"""

    @staticmethod
    def quick_setup() -> PersonalConfig:
        """Interactive setup for first-time users"""
        print("🎵 Chameleon Audio - Personal Setup")
        print("=" * 50)

        config = PersonalConfig()

        # Audio library location
        print(f"\n📁 Audio Library Location")
        print(f"   Default: {config.audio_library}")
        custom_path = input("   Custom path (or press Enter): ").strip()
        if custom_path:
            config.audio_library = custom_path

        # Performance mode
        print(f"\n⚡ Performance Mode")
        print("   1. Fast (maximum speed, higher CPU usage)")
        print("   2. Balanced (good speed, moderate CPU)")
        print("   3. Safe (slower, minimal CPU usage)")
        mode_choice = input("   Choose (1-3, default 2): ").strip()

        if mode_choice == "1":
            config.performance_mode = "fast"
        elif mode_choice == "3":
            config.performance_mode = "safe"

        # Auto-backup
        print(f"\n💾 Auto-Backup")
        backup_choice = input("   Enable automatic backups? (Y/n): ").strip().lower()
        config.auto_backup = backup_choice != 'n'

        # Create directories
        Path(config.audio_library).mkdir(parents=True, exist_ok=True)
        Path(config.output_directory).mkdir(parents=True, exist_ok=True)
        Path(config.temp_directory).mkdir(parents=True, exist_ok=True)

        if config.auto_backup:
            Path(config.backup_directory).mkdir(parents=True, exist_ok=True)

        # Save configuration
        config.save()

        print(f"\n✅ Setup Complete!")
        print(f"   Configuration saved to ~/.chameleon/personal_config.json")
        print(f"\n🚀 Quick Start Commands:")
        print(f"   python main.py personal analyze")
        print(f"   python main.py personal process --normalize")
        print(f"   python main.py personal batch")

        return config

    @staticmethod
    def create_quick_commands(config: PersonalConfig) -> None:
        """Create convenient shell aliases/scripts"""

        # Create bash aliases file
        aliases_file = Path.home() / ".chameleon" / "aliases.sh"

        aliases = f"""#!/bin/bash
# Chameleon Audio - Personal Quick Commands

# Activate virtual environment
alias chameleon-activate='source {Path.cwd()}/.venv/bin/activate'

# Quick operations
alias audio-analyze='python {Path.cwd()}/main.py analyze'
alias audio-normalize='python {Path.cwd()}/main.py process --normalize'
alias audio-denoise='python {Path.cwd()}/main.py process --denoise'
alias audio-batch='python {Path.cwd()}/main.py batch {config.audio_library}'

# Personal library management
alias audio-lib='cd {config.audio_library}'
alias audio-processed='cd {config.output_directory}'

# Server
alias audio-server='python {Path.cwd()}/main.py server --host 127.0.0.1 --port 8080'
"""

        with open(aliases_file, 'w') as f:
            f.write(aliases)

        # Create PowerShell script for Windows
        ps_file = Path.home() / ".chameleon" / "aliases.ps1"

        ps_script = f"""# Chameleon Audio - Personal Quick Commands

# Activate virtual environment
function Chameleon-Activate {{
    & "{Path.cwd()}\.venv\Scripts\Activate.ps1"
}}

# Quick operations
function Audio-Analyze {{
    python "{Path.cwd()}\main.py" analyze $args
}}

function Audio-Normalize {{
    python "{Path.cwd()}\main.py" process --normalize $args
}}

function Audio-Denoise {{
    python "{Path.cwd()}\main.py" process --denoise $args
}}

function Audio-Batch {{
    python "{Path.cwd()}\main.py" batch "{config.audio_library}" $args
}}

# Directory shortcuts
function Audio-Lib {{
    Set-Location "{config.audio_library}"
}}

function Audio-Processed {{
    Set-Location "{config.output_directory}"
}}
"""

        with open(ps_file, 'w') as f:
            f.write(ps_script)

        print(f"\n📝 Quick commands created:")
        print(f"   Linux/Mac: source ~/.chameleon/aliases.sh")
        print(f"   Windows: . ~/.chameleon/aliases.ps1")


class PersonalLibraryManager:
    """Manage personal audio library"""

    def __init__(self, config: PersonalConfig):
        self.config = config
        self.library_path = Path(config.audio_library)
        self.db_path = Path.home() / ".chameleon" / "library.json"
        self.library_db = self._load_db()

    def _load_db(self) -> Dict:
        """Load library database"""
        if self.db_path.exists():
            with open(self.db_path, 'r') as f:
                return json.load(f)
        return {"files": {}, "playlists": {}, "tags": {}}

    def _save_db(self) -> None:
        """Save library database"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.db_path, 'w') as f:
            json.dump(self.library_db, f, indent=2)

    def scan_library(self) -> Dict[str, Any]:
        """Scan audio library and update database"""
        from advanced_validation import DeepFileInspector

        inspector = DeepFileInspector()
        new_files = []
        updated_files = []

        for ext in self.config.supported_formats:
            for file_path in self.library_path.rglob(f"*{ext}"):
                file_key = str(file_path.relative_to(self.library_path))

                # Check if file is new or modified
                if file_key not in self.library_db["files"]:
                    # New file
                    result = inspector.inspect_file(file_path)

                    self.library_db["files"][file_key] = {
                        "path": str(file_path),
                        "checksum": result.checksum_sha256,
                        "size": result.size_bytes,
                        "metadata": result.metadata,
                        "added": str(Path(file_path).stat().st_mtime),
                        "tags": []
                    }
                    new_files.append(file_key)
                else:
                    # Check if modified
                    current_checksum = self.library_db["files"][file_key].get("checksum")
                    result = inspector.inspect_file(file_path)

                    if result.checksum_sha256 != current_checksum:
                        self.library_db["files"][file_key].update({
                            "checksum": result.checksum_sha256,
                            "size": result.size_bytes,
                            "metadata": result.metadata,
                            "modified": str(Path(file_path).stat().st_mtime)
                        })
                        updated_files.append(file_key)

        self._save_db()

        return {
            "total_files": len(self.library_db["files"]),
            "new_files": len(new_files),
            "updated_files": len(updated_files),
            "new": new_files[:10],  # Show first 10
            "updated": updated_files[:10]
        }

    def add_tags(self, file_pattern: str, tags: list) -> None:
        """Add tags to files matching pattern"""
        import fnmatch

        for file_key in self.library_db["files"]:
            if fnmatch.fnmatch(file_key, file_pattern):
                current_tags = self.library_db["files"][file_key].get("tags", [])
                self.library_db["files"][file_key]["tags"] = list(set(current_tags + tags))

        self._save_db()

    def create_playlist(self, name: str, file_list: list) -> None:
        """Create playlist from file list"""
        self.library_db["playlists"][name] = {
            "files": file_list,
            "created": str(Path.home().stat().st_mtime)
        }
        self._save_db()

    def search(self, query: str) -> list:
        """Search library by filename, tags, or metadata"""
        results = []

        for file_key, file_info in self.library_db["files"].items():
            # Search in filename
            if query.lower() in file_key.lower():
                results.append(file_key)
                continue

            # Search in tags
            if any(query.lower() in tag.lower() for tag in file_info.get("tags", [])):
                results.append(file_key)
                continue

        return results


class PersonalWorkflow:
    """Common personal workflows"""

    # NOTE: podcast_workflow and music_workflow were placeholders that printed
    # step banners and a "ready!" success line while performing no processing
    # at all -- the same claimed-capability-with-no-implementation pattern that
    # got AIMusicAnalyzer removed (see CHARTER.md §9). They have no callers.
    # Rather than keep code that reports success it did not earn, they now say
    # plainly that they are unimplemented and point at the commands that do
    # the work for real.

    @staticmethod
    def podcast_workflow(input_file: Path, output_dir: Path) -> None:
        """Not implemented. Use the CLI directly (see the message below)."""
        raise NotImplementedError(
            "PersonalWorkflow.podcast_workflow is not implemented. "
            "Use the CLI, which does this for real:\n"
            f"  chameleon process {input_file} --normalize --denoise "
            f"--output-dir {output_dir}"
        )

    @staticmethod
    def music_workflow(input_file: Path, output_dir: Path) -> None:
        """Not implemented. Use the CLI directly (see the message below)."""
        raise NotImplementedError(
            "PersonalWorkflow.music_workflow is not implemented. "
            "Use the CLI, which does this for real:\n"
            f"  chameleon analyze {input_file} --loudness\n"
            f"  chameleon process {input_file} --normalize --output-dir {output_dir}"
        )

    @staticmethod
    def backup_workflow(library_path: Path, backup_path: Path) -> None:
        """Backup audio library with verification"""
        from advanced_validation import IntegrityVerifier

        print("💾 Backup Workflow")

        # 1. Create manifest
        print("  [1/3] Creating integrity manifest...")
        verifier = IntegrityVerifier()
        files = list(library_path.rglob("*.wav"))
        manifest = verifier.create_manifest(files, "backup_manifest")

        # 2. Copy files
        print("  [2/3] Copying files...")
        import shutil
        for file in files:
            rel_path = file.relative_to(library_path)
            dest = backup_path / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file, dest)

        # 3. Verify
        print("  [3/3] Verifying backup...")
        valid, issues = verifier.verify_manifest(manifest)

        if valid:
            print("  ✅ Backup verified successfully!")
        else:
            print(f"  ⚠️ Backup issues: {issues}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "setup":
        # Run interactive setup
        PersonalSetup.quick_setup()
    else:
        # Load existing config
        config = PersonalConfig.load()
        print(f"Personal configuration loaded from ~/.chameleon/personal_config.json")
        print(f"Audio library: {config.audio_library}")
        print(f"Performance mode: {config.performance_mode}")

        # Create quick commands
        PersonalSetup.create_quick_commands(config)

        # Test library manager
        manager = PersonalLibraryManager(config)
        print("\nScanning library...")
        stats = manager.scan_library()
        print(f"Total files: {stats['total_files']}")
        print(f"New files: {stats['new_files']}")
        print(f"Updated files: {stats['updated_files']}")
