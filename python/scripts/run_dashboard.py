"""Run the local EWB web dashboard."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import uvicorn


def main() -> None:
    uvicorn.run("ewb.web_dashboard:app", host="127.0.0.1", port=8765, reload=False)


if __name__ == "__main__":
    main()
