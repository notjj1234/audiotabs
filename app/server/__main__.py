"""Run the desktop web server: ``python -m app.server --port 8533``."""

from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn

from .main import create_app


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.server")
    parser.add_argument("--port", type=int, default=8533)
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--token", type=str, default=None)
    args = parser.parse_args()

    app = create_app(data_dir=args.data_dir, token=args.token)
    uvicorn.run(app, host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
