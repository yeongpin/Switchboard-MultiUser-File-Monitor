#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Quick run script for Switchboard MultiUser File Monitor
"""

import sys
import os
from pathlib import Path

# Add src directory to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# Import and run main
from main import main

if __name__ == "__main__":
    main() 