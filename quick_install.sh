#!/bin/bash
# Chameleon Audio - Quick Install Script for Personal Use

echo "🎵 Chameleon Audio - Quick Install"
echo "=================================="
echo ""

# Check Python version
PYTHON_CMD=""
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "❌ Python 3.8+ is required but not found"
    exit 1
fi

PYTHON_VERSION=$($PYTHON_CMD -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "✓ Python $PYTHON_VERSION found"

# Create virtual environment
echo ""
echo "📦 Creating virtual environment..."
$PYTHON_CMD -m venv .venv

# Activate virtual environment
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
elif [ -f ".venv/Scripts/activate" ]; then
    source .venv/Scripts/activate
fi

# Install dependencies
echo ""
echo "📥 Installing dependencies..."
pip install --upgrade pip -q
pip install -r requirements.txt -q

echo ""
echo "✅ Installation complete!"
echo ""
echo "🚀 Next steps:"
echo "   1. Activate environment:"
echo "      source .venv/bin/activate"
echo ""
echo "   2. Run setup wizard:"
echo "      python personal_config.py setup"
echo ""
echo "   3. Load quick commands:"
echo "      source ~/.chameleon/aliases.sh"
echo ""
echo "   4. Start using:"
echo "      audio-analyze your_file.wav"
echo ""
