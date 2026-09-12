#!/usr/bin/env python3
"""Convenience root wrapper for scripts/import_offline_holdings.py."""

import os
import sys
from pathlib import Path

# Add backend to sys.path
backend_dir = Path(__file__).resolve().parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from scripts.import_offline_holdings import main

if __name__ == "__main__":
    main()
