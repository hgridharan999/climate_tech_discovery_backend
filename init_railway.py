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
        print("No data found. Run initial_setup.py to populate.")
    else:
        print("Database ready!")


if __name__ == "__main__":
    asyncio.run(main())
