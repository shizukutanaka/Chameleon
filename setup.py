#!/usr/bin/env python3
"""
Setup script for Chameleon Audio Processing
"""
from setuptools import setup, find_packages
from pathlib import Path

# Simple version - no dynamic versioning needed

# Read README
readme_file = Path(__file__).parent / "README.md"
long_description = ""
if readme_file.exists():
    long_description = readme_file.read_text(encoding="utf-8")

setup(
    name="chameleon-audio",
    version="2.0.0",
    author="Chameleon Team",
    description="High-performance audio processing system with real-time voice transformation and advanced effects",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Multimedia :: Sound/Audio",
        "Topic :: Multimedia :: Sound/Audio :: Speech",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=[
        "numpy>=1.20.0",
        "scipy>=1.7.0",
        "soundfile>=0.10.3",
        "sounddevice>=0.4.4",
        "pyyaml>=6.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=3.0.0",
        ],
        "performance": [
            "numba>=0.55.0",
            "psutil>=5.8.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "chameleon=main:main",
        ],
    },
    include_package_data=True,
)