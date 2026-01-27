"""Script to scrape real startup data from YC, Climatebase, and PitchBook."""

import sys
import asyncio
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.database import Database
from src.core.config import settings
from src.data.scraper import ClimateScraper


async def main():
    """Scrape startups from all configured sources."""
    print("=" * 60)
    print("Climate Startup Scraper")
    print("=" * 60)
    print()
    
    print("Initializing database...")
    db = Database(settings.database_path)
    
    print("Starting scraper...")
    async with ClimateScraper(db) as scraper:
        count = await scraper.scrape_all_sources()
        print(f"\n✓ Successfully scraped and saved {count} startups to database")
    
    print("\nDatabase statistics:")
    stats = db.get_stats()
    print(f"  Total startups: {stats['total_startups']}")
    print(f"  Verticals: {len(stats['verticals'])}")
    print("\n  Startups by vertical:")
    for vertical, count in sorted(
        stats["verticals"].items(), key=lambda x: x[1], reverse=True
    ):
        print(f"    - {vertical}: {count}")
    
    print("\n" + "=" * 60)
    print("Scraping complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
