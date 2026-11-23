.PHONY: help install ui desktop test ui-build dev-api dev-web

help:
	@echo "install   pip install -e '.[dev,demucs]'"
	@echo "ui-build  npm build of app/web into dist"
	@echo "dev-api   FastAPI on :8533"
	@echo "dev-web   Vite dev server (proxies /api)"
	@echo "ui        build web UI then remind how to run desktop"
	@echo "desktop   native window over FastAPI + Svelte (default)"
	@echo "test      pytest tests/ -q"

install:
	python -m pip install -e ".[dev,demucs]"

ui-build:
	cd app/web && npm ci && npm run build

dev-api:
	PYTHONPATH=src:. python -m app.server --port 8533

dev-web:
	cd app/web && npm run dev

ui: ui-build
	@echo "Web UI built. Run: make desktop   (or make dev-api + make dev-web)"

desktop:
	PYTHONPATH=src:. python packaging/launcher.py

test:
	PYTHONPATH=src:. python -m pytest tests/ -q
