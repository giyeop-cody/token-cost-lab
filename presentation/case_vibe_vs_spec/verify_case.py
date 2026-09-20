#!/usr/bin/env python3
"""Strict case deck verification (missing artifact/dependency fails)."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.verify_deck import main
if __name__ == '__main__':
    sys.argv[1:] = ['--pptx', str(Path(__file__).parent/'vibe_vs_spec.pptx'),
                    '--deck', 'case_vibe_vs_spec/vibe_vs_spec', *sys.argv[1:]]
    sys.exit(main())
