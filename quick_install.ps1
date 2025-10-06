# Chameleon Audio - Quick Install Script for Windows

Write-Host "🎵 Chameleon Audio - Quick Install" -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan
Write-Host ""

# Check Python
$pythonCmd = $null
if (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCmd = "python"
} elseif (Get-Command python3 -ErrorAction SilentlyContinue) {
    $pythonCmd = "python3"
} else {
    Write-Host "❌ Python 3.8+ is required but not found" -ForegroundColor Red
    exit 1
}

$pythonVersion = & $pythonCmd -c "import sys; print('.'.join(map(str, sys.version_info[:2])))"
Write-Host "✓ Python $pythonVersion found" -ForegroundColor Green

# Create virtual environment
Write-Host ""
Write-Host "📦 Creating virtual environment..." -ForegroundColor Yellow
& $pythonCmd -m venv .venv

# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Install dependencies
Write-Host ""
Write-Host "📥 Installing dependencies..." -ForegroundColor Yellow
pip install --upgrade pip -q
pip install -r requirements.txt -q

Write-Host ""
Write-Host "✅ Installation complete!" -ForegroundColor Green
Write-Host ""
Write-Host "🚀 Next steps:" -ForegroundColor Cyan
Write-Host "   1. Activate environment:"
Write-Host "      .\.venv\Scripts\Activate.ps1"
Write-Host ""
Write-Host "   2. Run setup wizard:"
Write-Host "      python personal_config.py setup"
Write-Host ""
Write-Host "   3. Load quick commands:"
Write-Host "      . ~/.chameleon/aliases.ps1"
Write-Host ""
Write-Host "   4. Start using:"
Write-Host "      Audio-Analyze your_file.wav"
Write-Host ""
