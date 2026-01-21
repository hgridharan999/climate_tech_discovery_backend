#!/usr/bin/env python
"""Initial setup script to create database and populate with sample data."""

import sys
import asyncio
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.config import settings
from src.core.database import Database
from src.core.logging import setup_logging
from src.data.scraper import ClimateScraper


async def main():
    """Run initial setup."""
    setup_logging("INFO")

    print("=" * 60)
    print("Climate Search API - Initial Setup")
    print("=" * 60)

    # Create data directories
    data_dir = settings.data_dir
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "embeddings").mkdir(exist_ok=True)

    print(f"\nData directory: {data_dir}")

    # Initialize database
    print("\n1. Initializing database...")
    db = Database(settings.database_path)
    print(f"   Database created at: {settings.database_path}")

    # Check if we already have data
    existing_count = db.get_startup_count()
    if existing_count > 0:
        print(f"   Found {existing_count} existing startups")
        response = input("   Do you want to add more sample data? (y/N): ")
        if response.lower() != "y":
            print("   Skipping data population")
            return

    # Populate with sample data
    print("\n2. Populating database with sample climate startups...")

    async with ClimateScraper(db) as scraper:
        # Try to scrape real data first
        print("   Attempting to scrape real data sources...")

        # Generate sample data (will work without API keys)
        sample_startups = scraper.generate_sample_data(count=500)

        saved = 0
        for startup in sample_startups:
            result = db.insert_startup(startup)
            if result:
                saved += 1

        print(f"   Saved {saved} startups to database")

    # Show stats
    print("\n3. Database statistics:")
    stats = db.get_stats()
    print(f"   Total startups: {stats['total_startups']}")
    print(f"   Verticals: {len(stats['verticals'])}")
    print("\n   Startups by vertical:")
    for vertical, count in sorted(
        stats["verticals"].items(), key=lambda x: x[1], reverse=True
    ):
        print(f"     - {vertical}: {count}")

    print("\n" + "=" * 60)
    print("Setup complete!")
    print("\nNext steps:")
    print("  1. Run 'python scripts/rebuild_index.py' to build search indexes")
    print("  2. Start the API with 'uvicorn src.api.main:app --reload'")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
