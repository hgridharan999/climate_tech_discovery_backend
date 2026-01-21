#!/usr/bin/env python3
"""Test that all imports work correctly."""

import sys
from pathlib import Path

# Add root to path
root = Path(__file__).parent
sys.path.insert(0, str(root))

print(f"Python path: {sys.path}")
print(f"Root directory: {root}")
print(f"src/data exists: {(root / 'src' / 'data').exists()}")
print(f"src/data/__init__.py exists: {(root / 'src' / 'data' / '__init__.py').exists()}")
print()

try:
    print("Testing: import src.data")
    import src.data
    print("✓ Success: src.data imported")
except ImportError as e:
    print(f"✗ Failed: {e}")

try:
    print("Testing: from src.data import CategoryMapper")
    from src.data import CategoryMapper
    print("✓ Success: CategoryMapper imported")
except ImportError as e:
    print(f"✗ Failed: {e}")

try:
    print("Testing: from src.data.category_mapper import CategoryMapper")
    from src.data.category_mapper import CategoryMapper
    print("✓ Success: CategoryMapper imported directly")
except ImportError as e:
    print(f"✗ Failed: {e}")

print("\nAll import tests completed!")
