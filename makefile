# Makefile for S3 Backup Automation Tool

APP_NAME=s3-backup
VENV?=.venv
PYTHON=$(VENV)/bin/python
PIP=$(VENV)/bin/pip

# Configuration
CONFIG=config.yaml

.PHONY: help venv install run dry-run lint clean format

help:
	@echo "Usage:"
	@echo "  make venv         Create virtual environment"
	@echo "  make install      Install Python dependencies"
	@echo "  make run          Run backup using config.yaml"
	@echo "  make dry-run      Simulate backup (no uploads)"
	@echo "  make lint         Run black and flake8 for linting"
	@echo "  make format       Auto-format code with black"
	@echo "  make clean        Remove .pyc files and __pycache__"

venv:
	@echo "🧪 Creating virtual environment..."
	python3 -m venv $(VENV)

install: venv
	@echo "📦 Installing dependencies..."
	$(PIP) install -r requirements.txt

run:
	@echo "🚀 Running backup with config..."
	$(PYTHON) backup.py --config $(CONFIG)

dry-run:
	@echo "🔍 Performing dry run..."
	$(PYTHON) backup.py --config $(CONFIG) --dry-run

lint:
	@echo "🧹 Linting with flake8 and black..."
	$(VENV)/bin/flake8 backup.py
	$(VENV)/bin/black --check backup.py

format:
	@echo "✨ Auto-formatting with black..."
	$(VENV)/bin/black backup.py

clean:
	@echo "🧼 Cleaning cache files..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -r {} +
