#!/usr/bin/env python3
"""
Setup script for Chameleon Voice Processor
"""

from setuptools import setup, find_packages
from pathlib import Path
import re

# Read version from __init__.py
def get_version():
    init_file = Path(__file__).parent / "__init__.py"
    if init_file.exists():
        content = init_file.read_text(encoding="utf-8")
        match = re.search(r'__version__ = ["\']([^"\']*)["\']', content)
        if match:
            return match.group(1)
    return "2.0.0"

# Read README for long description
readme_file = Path(__file__).parent / "README.md"
long_description = ""
if readme_file.exists():
    long_description = readme_file.read_text(encoding="utf-8")

setup(
    name="chameleon-voice",
    version=get_version(),
    author="Chameleon Development Team",
    description="Clean, simple, and efficient audio processing framework",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/chameleon-voice/chameleon",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Multimedia :: Sound/Audio",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=[
        "numpy>=1.21.0",
        "PyYAML>=6.0",
        "psutil>=5.9.0",
        "tqdm>=4.64.0",
    ],
    extras_require={
        "audio": [
            "soundfile>=0.12.0",
            "sounddevice>=0.4.0",
            "librosa>=0.10.0",
        ],
        "gui": [
            "matplotlib>=3.5.0",
        ],
        "dev": [
            "pytest>=7.0.0",
            "black>=22.0.0",
            "flake8>=4.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "chameleon=cli:main",
            "chameleon-gui=app:main",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["*.yaml", "*.yml", "*.md"],
    },
)