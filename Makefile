# V-SHIELD Makefile (SIH 2026)
# Enterprise automation for Code Quality, Testing, and Builds

.PHONY: help install lint format format-check test frontend-lint frontend-build check

PYTHON ?= python3
PYTEST ?= pytest
RUFF ?= ruff
BLACK ?= black
FLAKE8 ?= flake8

help:
	@echo "V-SHIELD Automation & Quality Gate Targets:"
	@echo "  make install        Install backend and frontend dependencies"
	@echo "  make lint           Run ruff, flake8, and frontend linter"
	@echo "  make format         Auto-format Python code using ruff and black"
	@echo "  make format-check   Verify formatting compliance"
	@echo "  make test           Execute pytest with coverage enforcement (>80%)"
	@echo "  make frontend-build Build production frontend artifacts"
	@echo "  make check          Run full CI quality gate (lint + format + test + build)"

install:
	pip install -r backend/requirements.txt
	cd frontend && npm ci

lint:
	$(RUFF) check backend/app tests/
	$(FLAKE8) backend/app tests/
	cd frontend && npm run lint

format:
	$(RUFF) check --fix backend/app tests/
	$(RUFF) format backend/app tests/
	$(BLACK) backend/app tests/

format-check:
	$(RUFF) check backend/app tests/
	$(BLACK) --check backend/app tests/

test:
	PYTHONPATH=backend $(PYTEST) tests/ -v --cov=backend/app --cov-report=term-missing --cov-report=xml --cov-fail-under=80

frontend-build:
	cd frontend && npm run build

check: lint format-check test frontend-build
