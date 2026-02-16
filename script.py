#!/usr/bin/env python3
"""
Printables Mass Downloader - Entry point

Usage:
    python script.py <URL> [options]

For full documentation, see README.md
"""

import sys
from printables.cli import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
