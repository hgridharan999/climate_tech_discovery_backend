"""Test script to debug YC scraper."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.scraper import ClimateScraper
from src.core.database import Database
from src.core.config import settings


async def test():
    """Test YC scraper."""
    db = Database(settings.database_path)
    async with ClimateScraper(db) as scraper:
        print("Testing YC scraper...")
        startups = await scraper.scrape_yc_climate()
        print(f"\nFound {len(startups)} startups")
        
        if startups:
            print("\nFirst 5 startups:")
            for i, startup in enumerate(startups[:5]):
                print(f"{i+1}. {startup.get('name')} - {startup.get('short_description', 'N/A')[:60]}")
        else:
            print("\nNo startups found - YC scraper may need updating")


if __name__ == "__main__":
    asyncio.run(test())
