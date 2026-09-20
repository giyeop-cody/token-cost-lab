#!/usr/bin/env python3
"""Compatibility entrypoint: regenerate all canonical decks/scripts together.
Keeps formerly split sources from drifting. See build_verified.py.
"""
from build_verified import main
if __name__ == "__main__":
    main()
