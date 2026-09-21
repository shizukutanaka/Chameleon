# Chameleon Audio - Quick Install Script for Windows

$ErrorActionPreference = "Stop"

Write-Host "🎵 Chameleon Audio - Quick Install" -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan
Write-Host ""

# Check Python -- and actually enforce the declared floor
# (requires-python >= 3.9: is_relative_to / builtin generics need it).
$pythonCmd = $null
if (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCmd = "python"
} elseif (Get-Command python3 -ErrorAction SilentlyContinue) {
    $pythonCmd = "python3"
} else {
    Write-Host "❌ Python 3.9+ is required but not found" -ForegroundColor Red
    exit 1
}

$pythonVersion = & $pythonCmd -c "import sys; print('.'.join(map(str, sys.version_info[:2])))"
& $pythonCmd -c "import sys; sys.exit(0 if sys.version_info[:2] >= (3, 9) else 1)"
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Python 3.9+ is required; found $pythonVersion" -ForegroundColor Red
    exit 1
}
Write-Host "✓ Python $pythonVersion found" -ForegroundColor Green

# Create virtual environment
Write-Host ""
Write-Host "📦 Creating virtual environment..." -ForegroundColor Yellow
& $pythonCmd -m venv .venv
if ($LASTEXITCODE -ne 0) { exit 1 }

# Install via the venv's own interpreter: `Activate.ps1` can be blocked by
# ExecutionPolicy, and `$ErrorActionPreference` does not cover native
# commands -- check $LASTEXITCODE so a failed install can't print success.
$venvPy = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    Write-Host "❌ venv creation produced no interpreter" -ForegroundColor Red
    exit 1
}

# requirements.txt is comments-only; `-e .` is the install that actually
# provides the `chameleon` command.
Write-Host ""
Write-Host "📥 Installing chameleon..." -ForegroundColor Yellow
& $venvPy -m pip install --upgrade pip -q
if ($LASTEXITCODE -ne 0) { exit 1 }
& $venvPy -m pip install -e . -q
if ($LASTEXITCODE -ne 0) { exit 1 }

Write-Host ""
Write-Host "✅ Installation complete!" -ForegroundColor Green
Write-Host ""
Write-Host "🚀 Next steps:" -ForegroundColor Cyan
Write-Host "   1. Activate environment:"
Write-Host "      .\.venv\Scripts\Activate.ps1"
Write-Host ""
Write-Host "   2. Run setup wizard:"
Write-Host "      .\.venv\Scripts\python.exe personal_config.py setup"
Write-Host ""
Write-Host "   3. Load quick commands:"
Write-Host "      . ~/.chameleon/aliases.ps1"
Write-Host ""
Write-Host "   4. Start using:"
Write-Host "      audio-analyze your_file.wav   # or: chameleon analyze your_file.wav"
Write-Host ""
