#!/usr/bin/env python3
"""Setup configuration for Chameleon Audio Processing System."""

from pathlib import Path
import re

from setuptools import setup, find_packages


ROOT = Path(__file__).resolve().parent
README = ROOT / "README.md"


def read_long_description() -> str:
    if README.exists():
        return README.read_text(encoding="utf-8")
    return "Chameleon Audio Processing System"


def read_version() -> str:
    """Extract version from main.py"""
    main_file = ROOT / "main.py"
    if main_file.exists():
        content = main_file.read_text(encoding="utf-8")
        match = re.search(r'VERSION\s*=\s*"([^"]+)"', content)
        if match:
            return match.group(1)
    return "1.0.0"


setup(
    name="chameleon-audio",
    version=read_version(),
    description="Professional audio processing toolkit for WAV files with security and auditability",
    long_description=read_long_description(),
    long_description_content_type="text/markdown",
    author="Chameleon Development Team",
    license="MIT",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Multimedia :: Sound/Audio",
        "Topic :: Multimedia :: Sound/Audio :: Analysis",
        "Topic :: Multimedia :: Sound/Audio :: Conversion",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
        "Environment :: Console",
    ],
    keywords=[
        "audio",
        "processing",
        "wav",
        "sound",
        "analysis",
        "batch-processing",
        "security",
        "midi",
    ],
    packages=find_packages(exclude=["tests*", "demo_plugins*"]),
    py_modules=[
        "main",
        "core",
        "security_validator",
        "advanced_validation",
        "plugin_system",
        "midi_analysis",
        "api_server",
        "batch_automation",
        "spectral_editor",
        "spectral_utils",
        "audio_restoration",
        "mastering_chain",
        "performance_optimizer",
        "ux_improvements",
    ],
    python_requires=">=3.8",
    install_requires=[
        # Core functionality works without dependencies
        # Optional dependencies listed in requirements.txt
    ],
    extras_require={
        "full": [
            "numpy>=1.20.0",
            "scipy>=1.7.0",
            "soundfile>=0.10.0",
            "librosa>=0.9.0",
        ],
        "midi": [
            "mido>=1.2.0",
        ],
        "realtime": [
            "pyaudio>=0.2.11",
        ],
        "api": [
            "fastapi>=0.70.0",
            "uvicorn>=0.15.0",
            # api_server.py's request models use pydantic v1 syntax
            # (Field(regex=...)), which raises at import under pydantic 2.
            "pydantic>=1.9,<2",
        ],
    },
    entry_points={
        "console_scripts": [
            "chameleon=main:cli",
        ],
    },
    include_package_data=True,
    zip_safe=False,
    project_urls={
        "Source": "https://github.com/shizukutanaka/Chameleon",
        "Issues": "https://github.com/shizukutanaka/Chameleon/issues",
    },
)
