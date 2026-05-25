#!/usr/bin/env python3
"""GPTPrime v2.0 — Launch the Strike Team"""
import sys
import os

# Ensure the root directory is in sys.path so 'gptprime' can be imported
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from gptprime.launcher import main
except ImportError as e:
    print(f"Error: Could not import gptprime.launcher. {e}")
    sys.exit(1)

if __name__ == "__main__":
    main()
