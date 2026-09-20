#!/usr/bin/env python3
"""Check regenerated text + text box bounds; visual review still required."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.verify_deck import main
if __name__ == '__main__': sys.exit(main())
