#!/usr/bin/env python
"""Initialize Railway deployment — populate database and build search indexes."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.core.config import settings
from src.core.database import Database
from src.core.logging import setup_logging


async def main():
    """Initialize database and search indexes for Railway deployment."""
    setup_logging("INFO")

    print("Checking database setup...")

    settings.data_dir.mkdir(parents=True, exist_ok=True)
    (settings.data_dir / "embeddings").mkdir(parents=True, exist_ok=True)

    db = Database(settings.database_path)
    existing_count = db.get_startup_count()
    print(f"Database initialized. Current startups: {existing_count}")

    if existing_count == 0:
        print("No data found. Populating database with startup data...")
        try:
            from src.data.scraper import ClimateScraper

            print("Starting scraper...")
            async with ClimateScraper(db) as scraper:
                print("Scraper initialized, fetching startups...")
                count = await scraper.scrape_all_sources()
                print(f"Scraper completed. Added {count} startups to database")

            final_count = db.get_startup_count()
            print(f"Verification: Database now has {final_count} startups")

            if final_count == 0:
                print("Warning: No startups from scraper. Generating sample data...")
                from src.data.scraper import ClimateScraper as CS
                async with CS(db) as scraper:
                    sample = scraper.generate_sample_data(count=300)
                    saved = sum(1 for s in sample if db.insert_startup(s))
                    final_count = db.get_startup_count()
                    print(f"Sample data: {saved} startups added. Total: {final_count}")

        except Exception as e:
            print(f"Error populating database: {e}")
            import traceback
            traceback.print_exc()
    else:
        print(f"Database already has {existing_count} startups.")

    # Always rebuild search index if we have data
    current_count = db.get_startup_count()
    if current_count > 0:
        print(f"\nBuilding search indexes for {current_count} startups...")
        try:
            from src.search.hybrid_search import HybridSearch

            search = HybridSearch(db)
            # Only rebuild if no existing index
            embeddings, startup_ids = search.embedder.load_embeddings()
            if embeddings is None or len(embeddings) != current_count:
                print("Rebuilding embeddings and FAISS index...")
                search.rebuild_index()
                print("Search indexes built successfully")
            else:
                print(f"Search indexes already exist ({len(embeddings)} vectors). Skipping rebuild.")
        except Exception as e:
            print(f"Warning: Could not build search index: {e}")
            print("The API will still work using BM25 keyword search.")
            import traceback
            traceback.print_exc()
    else:
        print("No startups in database — skipping index build.")


if __name__ == "__main__":
    asyncio.run(main())
