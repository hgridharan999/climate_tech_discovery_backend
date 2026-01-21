#!/usr/bin/env python3
"""Verify that all imports work correctly before deployment."""

import sys
from pathlib import Path

# Add project root to path
root_dir = Path(__file__).parent
sys.path.insert(0, str(root_dir))

def test_imports():
    """Test all critical imports."""
    print("Testing imports...")
    
    try:
        print("✓ Importing src.core.config...")
        from src.core.config import settings
        
        print("✓ Importing src.core.database...")
        from src.core.database import Database
        
        print("✓ Importing src.data.category_mapper...")
        from src.data.category_mapper import CategoryMapper
        
        print("✓ Importing src.data.scraper...")
        from src.data.scraper import ClimateScraper
        
        print("✓ Importing src.search modules...")
        from src.search.embedder import Embedder
        from src.search.hybrid_search import HybridSearchEngine
        
        print("✓ Importing src.api.main...")
        from src.api.main import app
        
        print("\n✅ All imports successful!")
        return True
        
    except ImportError as e:
        print(f"\n❌ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)
