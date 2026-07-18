#!/usr/bin/env python3
"""Main entry point for the Voice-to-PPT end-to-end workflow.

The implementation lives in ``src/voice_ppt_agent``; this wrapper preserves
the ``python run.py`` interface used in the final experiments.
"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from voice_ppt_agent.cli import run_main  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    """Run ASR and PowerPoint editing for one audio file or a directory."""

    return run_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
