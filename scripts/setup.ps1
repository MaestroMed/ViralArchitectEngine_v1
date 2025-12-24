# FORGE/LAB Setup Script for Windows
# Requires: PowerShell 5.1+, Node.js 18+, Python 3.11+, FFmpeg

param(
    [switch]$SkipPython,
    [switch]$SkipNode,
    [switch]$SkipFFmpeg
)

$ErrorActionPreference = "Stop"

Write-Host "╔══════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║           FORGE/LAB - Setup Script                       ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

function Test-Command($Command) {
    $oldPreference = $ErrorActionPreference
    $ErrorActionPreference = 'stop'
    try {
        if (Get-Command $Command) { return $true }
    }
    catch { return $false }
    finally { $ErrorActionPreference = $oldPreference }
}

# Check Node.js
if (-not $SkipNode) {
    Write-Host "[1/4] Checking Node.js..." -ForegroundColor Yellow
    if (Test-Command "node") {
        $nodeVersion = node --version
        Write-Host "  ✓ Node.js $nodeVersion found" -ForegroundColor Green
    } else {
        Write-Host "  ✗ Node.js not found. Please install Node.js 18+ from https://nodejs.org" -ForegroundColor Red
        exit 1
    }
}

# Check pnpm
Write-Host "[2/4] Checking pnpm..." -ForegroundColor Yellow
if (Test-Command "pnpm") {
    $pnpmVersion = pnpm --version
    Write-Host "  ✓ pnpm $pnpmVersion found" -ForegroundColor Green
} else {
    Write-Host "  → Installing pnpm..." -ForegroundColor Yellow
    npm install -g pnpm
    Write-Host "  ✓ pnpm installed" -ForegroundColor Green
}

# Check Python
if (-not $SkipPython) {
    Write-Host "[3/4] Checking Python..." -ForegroundColor Yellow
    if (Test-Command "python") {
        $pythonVersion = python --version
        Write-Host "  ✓ $pythonVersion found" -ForegroundColor Green
    } else {
        Write-Host "  ✗ Python not found. Please install Python 3.11+ from https://python.org" -ForegroundColor Red
        exit 1
    }
}

# Check FFmpeg
if (-not $SkipFFmpeg) {
    Write-Host "[4/4] Checking FFmpeg..." -ForegroundColor Yellow
    if (Test-Command "ffmpeg") {
        $ffmpegVersion = (ffmpeg -version | Select-String "ffmpeg version" | Out-String).Trim()
        Write-Host "  ✓ FFmpeg found" -ForegroundColor Green
    } else {
        Write-Host "  ✗ FFmpeg not found." -ForegroundColor Red
        Write-Host "    Please install FFmpeg:" -ForegroundColor Yellow
        Write-Host "    - winget install FFmpeg" -ForegroundColor Gray
        Write-Host "    - or download from https://ffmpeg.org/download.html" -ForegroundColor Gray
        exit 1
    }
}

Write-Host ""
Write-Host "Installing Node.js dependencies..." -ForegroundColor Yellow
pnpm install

Write-Host ""
Write-Host "Setting up Python virtual environment..." -ForegroundColor Yellow
$enginePath = Join-Path $PSScriptRoot "..\apps\forge-engine"
Push-Location $enginePath

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

# Activate and install
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt

Pop-Location

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║           Setup Complete!                                ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "To start development:" -ForegroundColor Cyan
Write-Host "  pnpm dev" -ForegroundColor White
Write-Host ""









