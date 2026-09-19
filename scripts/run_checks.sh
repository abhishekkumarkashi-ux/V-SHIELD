#!/usr/bin/env bash
# V-SHIELD Local CI Quality Gate Check Script (SIH 2026)
set -euo pipefail

echo "========================================================"
echo "🛡️  V-SHIELD Local Quality Gate & CI Pipeline Simulator"
echo "========================================================"

# Determine Python environment
if [ -d "backend/venv/bin" ]; then
    PYTEST="backend/venv/bin/pytest"
    RUFF="backend/venv/bin/ruff"
    BLACK="backend/venv/bin/black"
    FLAKE8="backend/venv/bin/flake8"
elif [ -d "backend/venv/Scripts" ]; then
    PYTEST="backend/venv/Scripts/pytest.exe"
    RUFF="backend/venv/Scripts/ruff.exe"
    BLACK="backend/venv/Scripts/black.exe"
    FLAKE8="backend/venv/Scripts/flake8.exe"
else
    PYTEST="pytest"
    RUFF="ruff"
    BLACK="black"
    FLAKE8="flake8"
fi

export PYTHONPATH="${PYTHONPATH:-.}:backend"

echo ""
echo "🔍 [1/4] Running Code Style & Linting Checks (Ruff, Flake8, Black)..."
$RUFF check backend/app tests/
$FLAKE8 backend/app tests/
$BLACK --check backend/app tests/
echo "✅ Backend linting and style checks passed."

echo ""
echo "⚛️  [2/4] Running Frontend Typecheck & Linting..."
(cd frontend && npm run lint)
echo "✅ Frontend type checks passed."

echo ""
echo "🏗️  [3/4] Running Frontend Production Build Check..."
(cd frontend && npm run build)
echo "✅ Frontend build passed."

echo ""
echo "🧪 [4/4] Running Backend Automated Tests with Coverage (>80%)..."
$PYTEST tests/ -v --cov=backend/app --cov-report=term-missing --cov-report=xml --cov-fail-under=80
echo "✅ All tests and coverage thresholds passed."

echo ""
echo "========================================================"
echo "🎉 ALL QUALITY GATES PASSED (Enterprise CI/CD Ready)!"
echo "========================================================"
