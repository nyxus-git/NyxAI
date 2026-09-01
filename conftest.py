"""
conftest.py (root)

Root-level pytest conftest that ensures the project root is on sys.path.
This allows all test files to import from 'core', 'tools', 'safety', etc.
without needing to install the package.
"""

import sys
from pathlib import Path

# Add the project root to sys.path so test modules can import project packages
sys.path.insert(0, str(Path(__file__).parent))
