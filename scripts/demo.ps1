# FORGE/LAB Demo Script
# Creates a demo project and generates sample clips

param(
    [Parameter(Mandatory=$false)]
    [string]$VideoPath,
    
    [Parameter(Mandatory=$false)]
    [int]$ClipCount = 3
)

$ErrorActionPreference = "Stop"

Write-Host "╔══════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║           FORGE/LAB - Demo Generator                     ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Check if engine is running
$enginePort = 7860
try {
    $response = Invoke-WebRequest -Uri "http://localhost:$enginePort/health" -UseBasicParsing -TimeoutSec 2
    Write-Host "✓ FORGE Engine is running on port $enginePort" -ForegroundColor Green
} catch {
    Write-Host "✗ FORGE Engine is not running." -ForegroundColor Red
    Write-Host "  Start it with: pnpm dev" -ForegroundColor Yellow
    exit 1
}

# Check video path
if (-not $VideoPath) {
    Write-Host ""
    Write-Host "Usage: .\demo.ps1 -VideoPath 'C:\path\to\video.mp4' [-ClipCount 3]" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "No video provided. Please provide a path to a video file:" -ForegroundColor Cyan
    $VideoPath = Read-Host "Video path"
}

if (-not (Test-Path $VideoPath)) {
    Write-Host "✗ Video file not found: $VideoPath" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Video: $VideoPath" -ForegroundColor Gray
Write-Host "Clips to generate: $ClipCount" -ForegroundColor Gray
Write-Host ""

# Create project
Write-Host "[1/5] Creating project..." -ForegroundColor Yellow
$createBody = @{
    name = "Demo Project - $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
    source_path = $VideoPath
} | ConvertTo-Json

$project = Invoke-RestMethod -Uri "http://localhost:$enginePort/v1/projects" `
    -Method Post -Body $createBody -ContentType "application/json"
$projectId = $project.id
Write-Host "  ✓ Project created: $projectId" -ForegroundColor Green

# Ingest
Write-Host "[2/5] Ingesting video..." -ForegroundColor Yellow
$ingestBody = @{
    create_proxy = $true
    extract_audio = $true
} | ConvertTo-Json

$ingestJob = Invoke-RestMethod -Uri "http://localhost:$enginePort/v1/projects/$projectId/ingest" `
    -Method Post -Body $ingestBody -ContentType "application/json"

# Wait for ingest
do {
    Start-Sleep -Seconds 2
    $jobStatus = Invoke-RestMethod -Uri "http://localhost:$enginePort/v1/jobs/$($ingestJob.job_id)"
    Write-Host "  Progress: $($jobStatus.progress)%" -ForegroundColor Gray
} while ($jobStatus.status -eq "running")

if ($jobStatus.status -ne "completed") {
    Write-Host "  ✗ Ingest failed: $($jobStatus.error)" -ForegroundColor Red
    exit 1
}
Write-Host "  ✓ Ingest complete" -ForegroundColor Green

# Analyze
Write-Host "[3/5] Analyzing for viral moments..." -ForegroundColor Yellow
$analyzeBody = @{
    transcribe = $true
    detect_scenes = $true
    analyze_audio = $true
    score_segments = $true
} | ConvertTo-Json

$analyzeJob = Invoke-RestMethod -Uri "http://localhost:$enginePort/v1/projects/$projectId/analyze" `
    -Method Post -Body $analyzeBody -ContentType "application/json"

# Wait for analysis
do {
    Start-Sleep -Seconds 3
    $jobStatus = Invoke-RestMethod -Uri "http://localhost:$enginePort/v1/jobs/$($analyzeJob.job_id)"
    Write-Host "  Progress: $($jobStatus.progress)% - $($jobStatus.stage)" -ForegroundColor Gray
} while ($jobStatus.status -eq "running")

if ($jobStatus.status -ne "completed") {
    Write-Host "  ✗ Analysis failed: $($jobStatus.error)" -ForegroundColor Red
    exit 1
}
Write-Host "  ✓ Analysis complete" -ForegroundColor Green

# Get top segments
Write-Host "[4/5] Selecting top $ClipCount segments..." -ForegroundColor Yellow
$segments = Invoke-RestMethod -Uri "http://localhost:$enginePort/v1/projects/$projectId/segments"
$topSegments = $segments | Sort-Object -Property score -Descending | Select-Object -First $ClipCount

foreach ($seg in $topSegments) {
    Write-Host "  - Score $($seg.score): $($seg.topic_label)" -ForegroundColor Gray
}

# Export clips
Write-Host "[5/5] Rendering clips..." -ForegroundColor Yellow
$exportJobs = @()

foreach ($seg in $topSegments) {
    $exportBody = @{
        segment_id = $seg.id
        variant = "A"
        include_captions = $true
        include_cover = $true
        include_metadata = $true
    } | ConvertTo-Json
    
    $exportJob = Invoke-RestMethod -Uri "http://localhost:$enginePort/v1/projects/$projectId/export" `
        -Method Post -Body $exportBody -ContentType "application/json"
    $exportJobs += $exportJob.job_id
}

# Wait for all exports
foreach ($jobId in $exportJobs) {
    do {
        Start-Sleep -Seconds 2
        $jobStatus = Invoke-RestMethod -Uri "http://localhost:$enginePort/v1/jobs/$jobId"
    } while ($jobStatus.status -eq "running")
    
    if ($jobStatus.status -eq "completed") {
        Write-Host "  ✓ Clip exported: $($jobStatus.output_path)" -ForegroundColor Green
    } else {
        Write-Host "  ✗ Export failed: $($jobStatus.error)" -ForegroundColor Red
    }
}

# Show results
Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║           Demo Complete!                                 ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""

$artifacts = Invoke-RestMethod -Uri "http://localhost:$enginePort/v1/projects/$projectId/artifacts"
Write-Host "Generated files:" -ForegroundColor Cyan
foreach ($artifact in $artifacts) {
    Write-Host "  $($artifact.path)" -ForegroundColor White
}
Write-Host ""









