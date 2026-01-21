#!/usr/bin/env python
"""Rebuild all search indexes from database."""

import sys
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.config import settings
from src.core.database import Database
from src.core.logging import setup_logging
from src.search.hybrid_search import HybridSearch


def main():
    """Rebuild search indexes."""
    setup_logging("INFO")

    print("=" * 60)
    print("Climate Search API - Rebuild Indexes")
    print("=" * 60)

    # Initialize database
    print("\n1. Connecting to database...")
    db = Database(settings.database_path)

    startup_count = db.get_startup_count()
    print(f"   Found {startup_count} startups in database")

    if startup_count == 0:
        print("\n   ERROR: No startups in database!")
        print("   Run 'python scripts/initial_setup.py' first")
        return

    # Initialize search engine
    print("\n2. Initializing search engine...")
    search = HybridSearch(db)

    # Rebuild indexes
    print("\n3. Rebuilding indexes (this may take a few minutes)...")
    start_time = time.time()

    search.rebuild_index()

    elapsed = time.time() - start_time
    print(f"\n   Indexes rebuilt in {elapsed:.2f} seconds")

    # Verify
    print("\n4. Verifying indexes...")
    stats = search.get_stats()
    print(f"   FAISS vectors: {stats['faiss']['total_vectors']}")
    print(f"   BM25 documents: {stats['bm25']['document_count']}")
    print(f"   Search initialized: {stats['is_initialized']}")

    # Test search
    print("\n5. Running test search...")
    test_query = "solar energy startup"
    results = search.search(test_query, top_k=5)

    print(f"   Query: '{test_query}'")
    print(f"   Results: {results['total_results']}")
    print(f"   Time: {results['processing_time_ms']:.2f}ms")

    if results["results"]:
        print("\n   Top results:")
        for i, result in enumerate(results["results"][:3], 1):
            startup = result["startup"]
            print(f"     {i}. {startup['name']} ({startup.get('primary_vertical', 'N/A')})")

    print("\n" + "=" * 60)
    print("Index rebuild complete!")
    print("\nYou can now start the API with:")
    print("  uvicorn src.api.main:app --host 0.0.0.0 --port 8000")
    print("=" * 60)


if __name__ == "__main__":
    main()
