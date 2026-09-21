#!/bin/bash
# Chameleon Audio - Quick Install Script for Personal Use

set -euo pipefail

echo "🎵 Chameleon Audio - Quick Install"
echo "=================================="
echo ""

# Check Python version -- and actually enforce it (pyproject declares
# requires-python >= 3.9; is_relative_to / builtin generics need it).
PYTHON_CMD=""
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "❌ Python 3.9+ is required but not found"
    exit 1
fi

PYTHON_VERSION=$($PYTHON_CMD -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
if ! $PYTHON_CMD -c 'import sys; sys.exit(0 if sys.version_info[:2] >= (3, 9) else 1)'; then
    echo "❌ Python 3.9+ is required; found $PYTHON_VERSION"
    exit 1
fi
echo "✓ Python $PYTHON_VERSION found"

# Create virtual environment
echo ""
echo "📦 Creating virtual environment..."
$PYTHON_CMD -m venv .venv

# Use the venv's own interpreter rather than relying on `activate`
# having succeeded (e.g. Windows execution-policy prompts) -- pip must
# install into .venv, not the system site-packages.
if [ -f ".venv/bin/python" ]; then
    VENV_PY=".venv/bin/python"
elif [ -f ".venv/Scripts/python.exe" ]; then
    VENV_PY=".venv/Scripts/python.exe"
else
    echo "❌ venv creation produced no interpreter (.venv/bin/python missing)"
    exit 1
fi

# Install the package itself: requirements.txt is comments-only, so
# `-r requirements.txt` installs nothing and `chameleon` never lands.
echo ""
echo "📥 Installing chameleon..."
"$VENV_PY" -m pip install --upgrade pip -q
"$VENV_PY" -m pip install -e . -q

echo ""
echo "✅ Installation complete!"
echo ""
echo "🚀 Next steps:"
echo "   1. Activate environment:"
echo "      source .venv/bin/activate"
echo ""
echo "   2. Run setup wizard:"
echo "      .venv/bin/python personal_config.py setup"
echo ""
echo "   3. Load quick commands:"
echo "      source ~/.chameleon/aliases.sh"
echo ""
echo "   4. Start using:"
echo "      audio-analyze your_file.wav   # or: chameleon analyze your_file.wav"
echo ""
