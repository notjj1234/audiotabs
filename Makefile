.PHONY: help install ui desktop test

help:
	@echo "install  pip install -e '.[dev,demucs]'"
	@echo "ui       streamlit run ui/app.py"
	@echo "desktop  native window (needs pip install -e '.[desktop]')"
	@echo "test     pytest tests/ -q"

install:
	python -m pip install -e ".[dev,demucs]"

ui:
	PYTHONPATH=src:. streamlit run ui/app.py

desktop:
	PYTHONPATH=src:. python packaging/launcher.py

test:
	PYTHONPATH=src:. python -m pytest tests/ -q
