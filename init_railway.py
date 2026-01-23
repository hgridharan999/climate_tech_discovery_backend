#!/usr/bin/env python
"""Initialize Railway deployment with sample data."""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from src.core.config import settings
from src.core.database import Database
from src.core.logging import setup_logging


async def main():
    """Initialize database for Railway deployment."""
    setup_logging("INFO")
    
    print("Checking database setup...")
    
    # Ensure data directory exists
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize database
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
                print(f"✓ Scraper completed. Added {count} startups to database")
            
            # Verify data was saved
            final_count = db.get_startup_count()
            print(f"✓ Verification: Database now has {final_count} startups")
            
            if final_count > 0:
                stats = db.get_stats()
                print(f"✓ Verticals: {stats.get('verticals', {})}")
            else:
                print("⚠ Warning: No startups were saved to database")
                
        except Exception as e:
            print(f"❌ Error populating database: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("Database ready!")


if __name__ == "__main__":
    asyncio.run(main())
