#!/usr/bin/env python3
"""
Advanced Validation Module for Production Systems
Deep file inspection and malware detection capabilities
"""

import os
import struct
import hashlib
import mmap
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass
import logging

logger = logging.getLogger("chameleon.validation")


@dataclass
class FileValidationResult:
    """Result of file validation"""
    is_valid: bool
    file_type: str
    size_bytes: int
    checksum_sha256: str
    warnings: List[str]
    errors: List[str]
    metadata: Dict


class DeepFileInspector:
    """Deep file inspection for security validation"""

    # WAV file magic numbers
    WAV_MAGIC = {
        b'RIFF': 'WAV',
        b'RIFX': 'WAV_BIG_ENDIAN'
    }

    # Suspicious patterns (executable code, scripts)
    SUSPICIOUS_PATTERNS = [
        b'MZ',  # DOS/Windows executable
        b'\x7fELF',  # Linux executable
        b'#!',  # Shell script
        b'<?php',  # PHP code
        b'<script',  # JavaScript
        b'import ',  # Python import
        b'eval(',  # Code evaluation
        b'exec(',  # Code execution
        b'system(',  # System command
        b'<html',  # HTML content
    ]

    def __init__(self, max_scan_bytes: int = 10 * 1024 * 1024):
        self.max_scan_bytes = max_scan_bytes

    def inspect_file(self, file_path: Path) -> FileValidationResult:
        """Perform deep inspection of file"""

        warnings = []
        errors = []
        metadata = {}

        try:
            # Get file stats
            stats = file_path.stat()
            size = stats.st_size

            # Calculate checksum
            checksum = self._calculate_checksum(file_path)

            # Validate file format
            file_type = self._identify_file_type(file_path)

            if file_type not in ('WAV', 'WAV_BIG_ENDIAN'):
                errors.append(f"Invalid file type: {file_type}")

            # Check for suspicious content
            suspicious = self._scan_for_suspicious_content(file_path)
            if suspicious:
                warnings.extend([f"Suspicious pattern: {p.decode('latin1', errors='ignore')}"
                               for p in suspicious])

            # Validate WAV structure
            if file_type.startswith('WAV'):
                wav_validation = self._validate_wav_structure(file_path)
                metadata.update(wav_validation)

            # Check file permissions
            if stats.st_mode & 0o111:  # Executable bit set
                warnings.append("File has executable permissions")

            # Check for hidden attributes (Unix)
            if file_path.name.startswith('.'):
                warnings.append("Hidden file")

            is_valid = len(errors) == 0

            return FileValidationResult(
                is_valid=is_valid,
                file_type=file_type,
                size_bytes=size,
                checksum_sha256=checksum,
                warnings=warnings,
                errors=errors,
                metadata=metadata
            )

        except Exception as e:
            logger.error(f"Inspection failed: {e}")
            return FileValidationResult(
                is_valid=False,
                file_type="UNKNOWN",
                size_bytes=0,
                checksum_sha256="",
                warnings=[],
                errors=[str(e)],
                metadata={}
            )

    def validate_for_processing(self, file_path: Path) -> FileValidationResult:
        """Lightweight format validation for the default batch/load path.

        Identical to ``inspect_file`` except it skips the full-file SHA-256
        checksum (``checksum_sha256`` is left empty), so it does not impose a
        whole-file read on every file in a batch. ``is_valid`` carries the same
        meaning as ``inspect_file``: it is False only when the magic number does
        not identify a real WAV container (e.g. an executable renamed to .wav).
        Suspicious byte patterns inside the data are reported as *warnings*, not
        errors — a WAV's PCM payload can legitimately contain those byte
        sequences — so callers should log them, not reject on them.
        """

        warnings: List[str] = []
        errors: List[str] = []
        metadata: Dict = {}

        try:
            stats = file_path.stat()
            size = stats.st_size

            file_type = self._identify_file_type(file_path)

            if file_type not in ('WAV', 'WAV_BIG_ENDIAN'):
                errors.append(f"Invalid file type: {file_type}")

            suspicious = self._scan_for_suspicious_content(file_path)
            if suspicious:
                warnings.extend([f"Suspicious pattern: {p.decode('latin1', errors='ignore')}"
                                 for p in suspicious])

            if file_type.startswith('WAV'):
                metadata.update(self._validate_wav_structure(file_path))

            if stats.st_mode & 0o111:
                warnings.append("File has executable permissions")

            if file_path.name.startswith('.'):
                warnings.append("Hidden file")

            return FileValidationResult(
                is_valid=len(errors) == 0,
                file_type=file_type,
                size_bytes=size,
                checksum_sha256="",
                warnings=warnings,
                errors=errors,
                metadata=metadata,
            )

        except Exception as e:
            logger.error(f"Format validation failed: {e}")
            return FileValidationResult(
                is_valid=False,
                file_type="UNKNOWN",
                size_bytes=0,
                checksum_sha256="",
                warnings=[],
                errors=[str(e)],
                metadata={},
            )

    def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA-256 checksum"""

        sha256 = hashlib.sha256()

        with open(file_path, 'rb') as f:
            # Read in chunks for large files
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)

        return sha256.hexdigest()

    def _identify_file_type(self, file_path: Path) -> str:
        """Identify file type by magic number"""

        with open(file_path, 'rb') as f:
            header = f.read(12)

        # Check WAV magic numbers
        for magic, file_type in self.WAV_MAGIC.items():
            if header.startswith(magic):
                # Verify WAVE format
                if header[8:12] == b'WAVE':
                    return file_type

        return "UNKNOWN"

    def _scan_for_suspicious_content(self, file_path: Path) -> List[bytes]:
        """Scan file for suspicious patterns"""

        found_patterns = []
        scan_size = min(self.max_scan_bytes, file_path.stat().st_size)

        try:
            with open(file_path, 'rb') as f:
                # Use memory mapping for efficient scanning
                if scan_size > 0:
                    with mmap.mmap(f.fileno(), scan_size, access=mmap.ACCESS_READ) as mm:
                        for pattern in self.SUSPICIOUS_PATTERNS:
                            if mm.find(pattern) != -1:
                                found_patterns.append(pattern)

        except Exception as e:
            logger.warning(f"Suspicious content scan failed: {e}")

        return found_patterns

    def _validate_wav_structure(self, file_path: Path) -> Dict:
        """Validate WAV file structure"""

        metadata = {}

        try:
            with open(file_path, 'rb') as f:
                # Read RIFF header
                riff_header = f.read(12)

                if len(riff_header) < 12:
                    return {"error": "Truncated RIFF header"}

                file_size = struct.unpack('<I', riff_header[4:8])[0]
                metadata["declared_size"] = file_size

                # Parse chunks
                chunks_found = []
                while True:
                    chunk_header = f.read(8)
                    if len(chunk_header) < 8:
                        break

                    chunk_id = chunk_header[:4]
                    chunk_size = struct.unpack('<I', chunk_header[4:8])[0]

                    chunks_found.append(chunk_id.decode('latin1', errors='ignore'))

                    if chunk_id == b'fmt ':
                        # Parse format chunk
                        fmt_data = f.read(min(chunk_size, 40))
                        if len(fmt_data) >= 16:
                            format_tag, channels, sample_rate, _, _, bits_per_sample = \
                                struct.unpack('<HHIIHH', fmt_data[:16])

                            metadata.update({
                                "format_tag": format_tag,
                                "channels": channels,
                                "sample_rate": sample_rate,
                                "bits_per_sample": bits_per_sample
                            })

                            # Validate format
                            if format_tag != 1:  # PCM
                                metadata["warning"] = f"Non-PCM format: {format_tag}"

                            if channels < 1 or channels > 8:
                                metadata["warning"] = f"Unusual channel count: {channels}"

                            if sample_rate not in [8000, 11025, 16000, 22050, 44100, 48000, 96000]:
                                metadata["warning"] = f"Non-standard sample rate: {sample_rate}"

                        # Skip any unread remainder of an oversized fmt body.
                        remainder = chunk_size - len(fmt_data)
                        if remainder > 0:
                            f.seek(remainder, 1)

                    else:
                        # Skip other chunks
                        f.seek(chunk_size, 1)

                    if chunk_size % 2 == 1:
                        f.seek(1, 1)  # RIFF pad byte after odd-sized chunks

                metadata["chunks"] = chunks_found

                # Verify required chunks
                if 'fmt ' not in chunks_found:
                    metadata["error"] = "Missing fmt chunk"
                if 'data' not in chunks_found:
                    metadata["error"] = "Missing data chunk"

        except Exception as e:
            metadata["error"] = str(e)

        return metadata


class IntegrityVerifier:
    """File integrity verification and tamper detection"""

    def __init__(self, manifest_dir: Optional[Path] = None):
        self.manifest_dir = manifest_dir or Path.home() / ".chameleon" / "manifests"
        self.manifest_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

    def create_manifest(self, files: List[Path], manifest_name: str) -> Path:
        """Create integrity manifest for files"""

        manifest = {}

        for file_path in files:
            if not file_path.exists():
                continue

            inspector = DeepFileInspector()
            result = inspector.inspect_file(file_path)

            manifest[str(file_path)] = {
                "checksum": result.checksum_sha256,
                "size": result.size_bytes,
                "file_type": result.file_type,
                "metadata": result.metadata
            }

        # Save manifest
        manifest_path = self.manifest_dir / f"{manifest_name}.json"
        import json
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)

        os.chmod(manifest_path, 0o600)
        logger.info(f"Manifest created: {manifest_path}")

        return manifest_path

    def verify_manifest(self, manifest_path: Path) -> Tuple[bool, List[str]]:
        """Verify files against manifest"""

        import json

        with open(manifest_path, 'r') as f:
            manifest = json.load(f)

        all_valid = True
        issues = []

        for file_path_str, expected in manifest.items():
            file_path = Path(file_path_str)

            if not file_path.exists():
                all_valid = False
                issues.append(f"Missing: {file_path}")
                continue

            # Verify checksum
            inspector = DeepFileInspector()
            result = inspector.inspect_file(file_path)

            if result.checksum_sha256 != expected["checksum"]:
                all_valid = False
                issues.append(f"Checksum mismatch: {file_path}")

            if result.size_bytes != expected["size"]:
                all_valid = False
                issues.append(f"Size mismatch: {file_path}")

        return all_valid, issues


class SanitizationEngine:
    """File sanitization and content cleaning"""

    @staticmethod
    def sanitize_wav_metadata(file_path: Path, output_path: Path) -> None:
        """Remove metadata chunks from WAV file"""

        KEEP_CHUNKS = {b'RIFF', b'WAVE', b'fmt ', b'data'}

        with open(file_path, 'rb') as infile, open(output_path, 'wb') as outfile:
            # Read and write RIFF header
            riff_header = infile.read(12)
            outfile.write(riff_header[:4])  # RIFF

            # We'll update size later
            size_pos = outfile.tell()
            outfile.write(b'\x00\x00\x00\x00')  # Placeholder

            outfile.write(riff_header[8:12])  # WAVE

            total_size = 4  # WAVE tag

            # Process chunks
            while True:
                chunk_header = infile.read(8)
                if len(chunk_header) < 8:
                    break

                chunk_id = chunk_header[:4]
                chunk_size = struct.unpack('<I', chunk_header[4:8])[0]

                # Only keep essential chunks
                if chunk_id in KEEP_CHUNKS:
                    outfile.write(chunk_header)
                    chunk_data = infile.read(chunk_size)
                    outfile.write(chunk_data)
                    total_size += 8 + chunk_size

                    # Pad to even boundary
                    if chunk_size % 2:
                        outfile.write(b'\x00')
                        total_size += 1
                else:
                    # Skip metadata chunk
                    infile.seek(chunk_size, 1)
                    logger.info(f"Removed chunk: {chunk_id.decode('latin1', errors='ignore')}")

            # Update file size
            outfile.seek(size_pos)
            outfile.write(struct.pack('<I', total_size))

        os.chmod(output_path, 0o600)
        logger.info(f"Sanitized: {file_path} -> {output_path}")


if __name__ == "__main__":
    print("Testing Advanced Validation Module...")

    # Create test WAV file
    from validation_test import create_test_wav
    test_file = Path("test_validation.wav")
    create_test_wav(str(test_file))

    # Test deep inspection
    inspector = DeepFileInspector()
    result = inspector.inspect_file(test_file)

    print(f"\nValidation Result:")
    print(f"  Valid: {result.is_valid}")
    print(f"  Type: {result.file_type}")
    print(f"  Size: {result.size_bytes}")
    print(f"  Checksum: {result.checksum_sha256[:16]}...")
    print(f"  Warnings: {result.warnings}")
    print(f"  Metadata: {result.metadata}")

    # Test manifest creation
    verifier = IntegrityVerifier()
    manifest_path = verifier.create_manifest([test_file], "test_manifest")
    print(f"\nManifest created: {manifest_path}")

    # Verify manifest
    valid, issues = verifier.verify_manifest(manifest_path)
    print(f"Verification: {valid}, Issues: {issues}")

    # Test sanitization
    sanitized_file = Path("test_sanitized.wav")
    SanitizationEngine.sanitize_wav_metadata(test_file, sanitized_file)

    # Cleanup
    test_file.unlink()
    sanitized_file.unlink()

    print("\nAdvanced validation tests completed")
