.PHONY: help install ui desktop test

help:
	@echo "install  pip install -e '.[dev,demucs]'"
	@echo "ui       streamlit run ui/app.py"
	@echo "desktop  native window (needs pip install -e '.[desktop]')"
	@echo "test     pytest tests/ -q"

install:
	python -m pip install -e ".[dev,demucs]"

ui-build:
	cd app/web && npm ci && npm run build

dev-api:
	PYTHONPATH=src:. python -m app.server --port 8533

dev-web:
	cd app/web && npm run dev

ui:
	PYTHONPATH=src:. streamlit run ui/app.py

desktop:
	PYTHONPATH=src:. python packaging/launcher.py

test:
	PYTHONPATH=src:. python -m pytest tests/ -q
