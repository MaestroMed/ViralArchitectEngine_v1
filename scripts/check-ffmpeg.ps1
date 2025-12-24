# Check FFmpeg installation and capabilities

$ErrorActionPreference = "Stop"

Write-Host "╔══════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║           FFmpeg Capability Check                        ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

function Test-Command($Command) {
    try {
        if (Get-Command $Command -ErrorAction SilentlyContinue) { return $true }
    } catch { return $false }
    return $false
}

# Check FFmpeg
Write-Host "[FFmpeg]" -ForegroundColor Yellow
if (Test-Command "ffmpeg") {
    $ffmpegPath = (Get-Command ffmpeg).Source
    Write-Host "  Location: $ffmpegPath" -ForegroundColor Gray
    
    $version = ffmpeg -version 2>&1 | Select-Object -First 1
    Write-Host "  $version" -ForegroundColor Green
    
    # Check for NVENC
    Write-Host ""
    Write-Host "[NVENC Support]" -ForegroundColor Yellow
    $encoders = ffmpeg -encoders 2>&1 | Out-String
    
    if ($encoders -match "h264_nvenc") {
        Write-Host "  ✓ h264_nvenc (NVIDIA H.264) - Available" -ForegroundColor Green
    } else {
        Write-Host "  ✗ h264_nvenc - Not available (will use libx264)" -ForegroundColor Yellow
    }
    
    if ($encoders -match "hevc_nvenc") {
        Write-Host "  ✓ hevc_nvenc (NVIDIA H.265) - Available" -ForegroundColor Green
    } else {
        Write-Host "  ✗ hevc_nvenc - Not available" -ForegroundColor Gray
    }
    
    # Check for libass
    Write-Host ""
    Write-Host "[Subtitle Filters]" -ForegroundColor Yellow
    $filters = ffmpeg -filters 2>&1 | Out-String
    
    if ($filters -match "ass") {
        Write-Host "  ✓ ASS/SSA subtitle filter - Available" -ForegroundColor Green
    } else {
        Write-Host "  ✗ ASS filter - Not available" -ForegroundColor Red
    }
    
    if ($filters -match "subtitles") {
        Write-Host "  ✓ Subtitles filter - Available" -ForegroundColor Green
    } else {
        Write-Host "  ✗ Subtitles filter - Not available" -ForegroundColor Red
    }
    
} else {
    Write-Host "  ✗ FFmpeg not found in PATH" -ForegroundColor Red
    Write-Host ""
    Write-Host "Install FFmpeg:" -ForegroundColor Yellow
    Write-Host "  winget install FFmpeg" -ForegroundColor White
    Write-Host "  - or -" -ForegroundColor Gray
    Write-Host "  Download from https://ffmpeg.org/download.html" -ForegroundColor White
    exit 1
}

# Check FFprobe
Write-Host ""
Write-Host "[FFprobe]" -ForegroundColor Yellow
if (Test-Command "ffprobe") {
    Write-Host "  ✓ Available" -ForegroundColor Green
} else {
    Write-Host "  ✗ Not found (should be included with FFmpeg)" -ForegroundColor Red
}

Write-Host ""
Write-Host "Check complete." -ForegroundColor Cyan









