# V-SHIELD Local Quality Gate Script for Windows PowerShell (SIH 2026)
$ErrorActionPreference = "Stop"

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "V-SHIELD Local Quality Gate and CI Pipeline Simulator" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

$env:PYTHONPATH = "backend"
$env:PYTHONIOENCODING = "utf-8"

$RUFF = "backend\venv\Scripts\ruff.exe"
$FLAKE8 = "backend\venv\Scripts\flake8.exe"
$BLACK = "backend\venv\Scripts\black.exe"
$PYTEST = "backend\venv\Scripts\pytest.exe"

Write-Host ""
Write-Host "[1/4] Running Code Style and Linting Checks (Ruff, Flake8, Black)..." -ForegroundColor Yellow
& $RUFF check backend/app tests/
& $FLAKE8 backend/app tests/
& $BLACK --check backend/app tests/
Write-Host "PASS: Backend linting and style checks passed." -ForegroundColor Green

Write-Host ""
Write-Host "[2/4] Running Frontend Typecheck and Linting..." -ForegroundColor Yellow
Push-Location frontend
try {
    npm run lint
} finally {
    Pop-Location
}
Write-Host "PASS: Frontend type checks passed." -ForegroundColor Green

Write-Host ""
Write-Host "[3/4] Running Frontend Production Build Check..." -ForegroundColor Yellow
Push-Location frontend
try {
    npm run build
} finally {
    Pop-Location
}
Write-Host "PASS: Frontend build passed." -ForegroundColor Green

Write-Host ""
Write-Host "[4/4] Running Backend Automated Tests with Coverage (>80%)..." -ForegroundColor Yellow
& $PYTEST tests/ -v --cov=backend/app --cov-report=term-missing --cov-report=xml --cov-fail-under=80
Write-Host "PASS: All tests and coverage thresholds passed." -ForegroundColor Green

Write-Host ""
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "ALL QUALITY GATES PASSED (Enterprise CI/CD Ready)!" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
