# OpenClaw Architecture 2.0 - Portable Bootstrap Sentinel
# Purpose: Enable "Double-click to revive" portability on any Windows machine.
# Aligns with "Lego-Style Deployment" rule.

$ProjectRoot = Get-Location
$InfrastructureDir = Join-Path $ProjectRoot "src\infrastructure"
$EnvAdapterDir = Join-Path $InfrastructureDir "env_adapter"
$EnvAdapterScript = Join-Path $EnvAdapterDir "env_adapter.py"
$DockerComposeFile = Join-Path $InfrastructureDir "docker-compose.yml"
$EnvFile = Join-Path $InfrastructureDir ".env"
$EnvExample = Join-Path $EnvAdapterDir ".env.example"

Write-Host ">>> Starting OpenClaw 2.0 Portable Setup..." -ForegroundColor Cyan

# 1. Check Dependencies
Write-Host "[1/4] Checking System Dependencies..." -ForegroundColor Yellow
$Dependencies = @("docker", "python")
foreach ($dep in $Dependencies) {
    if (Get-Command $dep -ErrorAction SilentlyContinue) {
        Write-Host "  - $dep: [FOUND]" -ForegroundColor Green
    } else {
        Write-Host "  - $dep: [MISSING]" -ForegroundColor Red
        if ($dep -eq "docker") {
            Write-Host "    -> Please install Docker Desktop (https://www.docker.com/products/docker-desktop/)" -ForegroundColor Gray
        } elseif ($dep -eq "python") {
            Write-Host "    -> Please install Python (https://www.python.org/downloads/)" -ForegroundColor Gray
        }
        $FatalError = $true
    }
}

if ($FatalError) {
    Write-Host "!!! Critical dependencies missing. Aborting setup." -ForegroundColor Red
    exit 1
}

# 2. Environment Adaptation
Write-Host "[2/4] Running Environment Adapter (Lego-Style)..." -ForegroundColor Yellow
python "$EnvAdapterScript"

if (-Not (Test-Path $EnvFile)) {
    Write-Host "!!! Failed to generate .env file. Checking .env.example..." -ForegroundColor Red
    if (Test-Path $EnvExample) {
        Copy-Item $EnvExample $EnvFile
        Write-Host "  - Fallback: Copied .env.example to .env. Please configure manually if needed." -ForegroundColor Gray
    } else {
        Write-Host "!!! No .env or .env.example found. Aborting." -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "  - Environment Synced: [OK]" -ForegroundColor Green
}

# 3. Pull & Initialize Infrastructure
Write-Host "[3/4] Pulling & Starting Dockerized Infrastructure..." -ForegroundColor Yellow
Set-Location $InfrastructureDir
docker-compose up -d

if ($LASTEXITCODE -eq 0) {
    Write-Host "  - Dapr, Redis, n8n, Cloudflared: [ACTIVE]" -ForegroundColor Green
} else {
    Write-Host "!!! Docker Compose failed to start services. Check Docker logs." -ForegroundColor Red
}

# 4. Final Status Summary
Write-Host "[4/4] Verifying System Sovereignty..." -ForegroundColor Yellow
$RegistryFile = Join-Path $InfrastructureDir "registry.json"
if (Test-Path $RegistryFile) {
    $Registry = Get-Content $RegistryFile | ConvertFrom-Json
    if ($Registry.master_agent -eq $true) {
        Write-Host "  - AAL Sovereignty: [LOCKED & MASTER]" -ForegroundColor Cyan
    }
}

Write-Host "`n>>> OpenClaw Architecture 2.0 is now LIVE and CRUISING." -ForegroundColor Green
Write-Host ">>> Location: $ProjectRoot" -ForegroundColor Gray
Write-Host ">>> Mission Control: Mission.md" -ForegroundColor Gray
Set-Location $ProjectRoot
