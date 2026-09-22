#!/usr/bin/env python3
"""
Personal Use Configuration - Optimized for Individual Users
Simplified setup with maximum security and features
"""

import sys
import os
import json
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict, fields
from datetime import datetime, timezone
import logging

logger = logging.getLogger("chameleon.personal")


def _atomic_write_text(path: Path, content: str) -> None:
    """Write text to path atomically: sibling temp file + os.replace.

    A plain open('w') truncates first, so a crash or kill mid-write left a
    half-written JSON that PersonalConfig.load then reported as corrupt --
    the user's settings were lost *and* named as their fault. os.replace
    is atomic on POSIX and Windows: readers see the old file or the new
    one, never a partial write.
    """
    tmp = path.parent / (path.name + ".tmp")
    with open(tmp, 'w') as f:
        f.write(content)
    os.replace(tmp, path)


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
        """Load personal configuration, or write a default one if none exists.

        Tolerates a config written by a different version of Chameleon: keys
        this version does not recognise are reported and ignored rather than
        raising. `cls(**data)` on its own turned an extra key into a bare
        `TypeError: __init__() got an unexpected keyword argument`, so
        downgrading -- or hand-editing the file, which is the whole point of a
        personal config -- left the tool unable to start.

        A file that is not valid JSON is a different matter and is reported as
        such, naming the path, rather than silently replacing the user's
        settings with defaults.
        """
        if config_path is None:
            config_path = Path.home() / ".chameleon" / "personal_config.json"

        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    data = json.load(f)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"{config_path} is not valid JSON ({exc}). Fix it, or delete "
                    "it to start again from the defaults."
                ) from exc

            if not isinstance(data, dict):
                raise ValueError(
                    f"{config_path} should contain a JSON object, found "
                    f"{type(data).__name__}."
                )

            known = {field.name for field in fields(cls)}
            unknown = sorted(set(data) - known)
            if unknown:
                logger.warning(
                    "Ignoring unrecognised setting(s) in %s: %s",
                    config_path, ", ".join(unknown)
                )
            return cls(**{key: value for key, value in data.items() if key in known})

        # Create default config
        config = cls()
        config.save(config_path)
        return config

    def save(self, config_path: Optional[Path] = None) -> None:
        """Save personal configuration"""
        if config_path is None:
            config_path = Path.home() / ".chameleon" / "personal_config.json"

        config_path.parent.mkdir(parents=True, exist_ok=True)

        _atomic_write_text(config_path, json.dumps(asdict(self), indent=2))

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

        # Write the shell aliases this method's own printed instructions
        # below rely on. This used to be missing: `main.py` has no `personal`
        # subcommand -- `python main.py personal analyze` is an argparse
        # "invalid choice" (exit 2) -- and this call lived only in the bare
        # `python personal_config.py` branch of __main__, never in the `setup`
        # command that quick_install.sh/.ps1 document as the onboarding step.
        # A user following the documented flow got directions that did not
        # run and never received the aliases file quick_install.sh's own next
        # step tells them to source. See CHARTER.md §9.
        PersonalSetup.create_quick_commands(config)

        print(f"\n✅ Setup Complete!")
        print(f"   Configuration saved to ~/.chameleon/personal_config.json")
        print(f"\n🚀 Quick Start Commands:")
        print(f"   source ~/.chameleon/aliases.sh   # Linux/Mac -- or aliases.ps1 on Windows")
        print(f"   audio-analyze your_file.wav")
        print(f"   audio-batch analyze          # scans {config.audio_library}")
        print(f"\n   ...or directly, with no aliases loaded:")
        print(f"   {sys.executable} main.py analyze your_file.wav")
        print(f"   {sys.executable} main.py batch {config.audio_library} analyze")

        return config

    @staticmethod
    def create_quick_commands(config: PersonalConfig) -> None:
        """Create convenient shell aliases/scripts"""

        # Create bash aliases file. The .chameleon directory is not
        # guaranteed to exist here -- callers that skip PersonalConfig.save()
        # (or run this method standalone) would otherwise get a
        # FileNotFoundError.
        aliases_file = Path.home() / ".chameleon" / "aliases.sh"
        aliases_file.parent.mkdir(parents=True, exist_ok=True)

        # The aliases must invoke the interpreter that ran setup, not a bare
        # `python`: on systems with only `python3` (or no activated venv in
        # the new shell) a literal `python` does not resolve and every alias
        # fails with "command not found". sys.executable is also venv-aware,
        # so the aliases keep working without `chameleon-activate` first.
        aliases = f"""#!/bin/bash
# Chameleon Audio - Personal Quick Commands

# Activate virtual environment
alias chameleon-activate='source {Path.cwd()}/.venv/bin/activate'

# Quick operations
alias audio-analyze='"{sys.executable}" "{Path.cwd()}/main.py" analyze'
alias audio-normalize='"{sys.executable}" "{Path.cwd()}/main.py" process --normalize'
alias audio-denoise='"{sys.executable}" "{Path.cwd()}/main.py" process --denoise'
alias audio-batch='"{sys.executable}" "{Path.cwd()}/main.py" batch "{config.audio_library}"'

# Personal library management
alias audio-lib='cd {config.audio_library}'
alias audio-processed='cd {config.output_directory}'

# Server
alias audio-server='"{sys.executable}" "{Path.cwd()}/main.py" server --host 127.0.0.1 --port 8080'
"""

        _atomic_write_text(aliases_file, aliases)

        # Create PowerShell script for Windows
        ps_file = Path.home() / ".chameleon" / "aliases.ps1"

        # Raw f-string: the Windows paths inside are written with literal
        # backslashes (\m, \S, ...), which CPython 3.12+ reports as invalid
        # escape sequences.
        ps_script = rf"""# Chameleon Audio - Personal Quick Commands

# Activate virtual environment
function Chameleon-Activate {{
    & "{Path.cwd()}\.venv\Scripts\Activate.ps1"
}}

# Quick operations
function Audio-Analyze {{
    & "{sys.executable}" "{Path.cwd()}\main.py" analyze $args
}}

function Audio-Normalize {{
    & "{sys.executable}" "{Path.cwd()}\main.py" process --normalize $args
}}

function Audio-Denoise {{
    & "{sys.executable}" "{Path.cwd()}\main.py" process --denoise $args
}}

function Audio-Batch {{
    & "{sys.executable}" "{Path.cwd()}\main.py" batch "{config.audio_library}" $args
}}

# Directory shortcuts
function Audio-Lib {{
    Set-Location "{config.audio_library}"
}}

function Audio-Processed {{
    Set-Location "{config.output_directory}"
}}
"""

        _atomic_write_text(ps_file, ps_script)

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
        """Load library database.

        Same rigor as PersonalConfig.load: a corrupt file must say so and
        offer recovery, not die on a raw JSONDecodeError traceback."""
        if self.db_path.exists():
            try:
                with open(self.db_path, 'r') as f:
                    data = json.load(f)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"{self.db_path} is not valid JSON ({exc}). Fix it, or "
                    "delete it to start again from an empty library."
                ) from exc
            if not isinstance(data, dict):
                raise ValueError(
                    f"{self.db_path} should contain a JSON object, found "
                    f"{type(data).__name__}."
                )
            return data
        return {"files": {}, "playlists": {}, "tags": {}}

    def _save_db(self) -> None:
        """Save library database"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write_text(self.db_path, json.dumps(self.library_db, indent=2))

    def scan_library(self) -> Dict[str, Any]:
        """Scan audio library and update database"""
        from advanced_validation import DeepFileInspector

        inspector = DeepFileInspector()
        new_files = []
        updated_files = []

        # rglob's literal match is case-sensitive ("*.wav" misses ".WAV");
        # gather once and let the lowered-suffix test decide, same as the
        # CLI and core batch gathers.
        supported = {e.lower() for e in self.config.supported_formats}
        for file_path in self.library_path.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in supported:
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
                # set() orders by hash seed, so the saved db got a different
                # tag order every session for identical input. dict.fromkeys
                # dedupes while keeping the existing order.
                self.library_db["files"][file_key]["tags"] = list(
                    dict.fromkeys(current_tags + tags))

        self._save_db()

    def create_playlist(self, name: str, file_list: list) -> None:
        """Create playlist from file list"""
        # The timestamp used to be `Path.home().stat().st_mtime` -- the home
        # directory's modification time, which is the same value for every
        # playlist ever created and has nothing to do with when this one was.
        self.library_db["playlists"][name] = {
            "files": file_list,
            "created": datetime.now(timezone.utc).isoformat()
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
        # Same case-sensitivity trap as scan_library: "*.wav" misses ".WAV".
        files = [p for p in library_path.rglob("*")
                 if p.is_file() and p.suffix.lower() in (".wav", ".wave")]
        manifest_path = verifier.create_manifest(files, "backup_manifest")

        # 2. Copy files
        print("  [2/3] Copying files...")
        import shutil
        for file in files:
            rel_path = file.relative_to(library_path)
            dest = backup_path / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file, dest)

        # 3. Verify -- the manifest keys on SOURCE paths, so
        # verify_manifest() would re-check the originals and could never
        # notice a corrupt or missing copy. Re-inspect each destination
        # file and compare it against the recorded source checksum.
        print("  [3/3] Verifying backup...")
        import json
        from advanced_validation import DeepFileInspector
        with open(manifest_path) as f:
            expected = json.load(f)
        inspector = DeepFileInspector()
        issues = []
        for file in files:
            rel_path = file.relative_to(library_path)
            dest = backup_path / rel_path
            entry = expected.get(str(file))
            if not dest.exists():
                issues.append(f"missing copy: {rel_path}")
            elif entry is None:
                issues.append(f"no manifest entry: {rel_path}")
            elif inspector.inspect_file(dest).checksum_sha256 != entry["checksum"]:
                issues.append(f"checksum mismatch: {rel_path}")

        if not issues:
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
