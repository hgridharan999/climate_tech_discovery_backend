"""Web scrapers for climate startup data from various sources."""

import asyncio
import logging
import re
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from urllib.parse import urljoin, urlparse

import aiohttp
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

from ..core.config import settings
from ..core.database import Database
from .category_mapper import CategoryMapper

logger = logging.getLogger(__name__)


class ClimateScraper:
    """Scrapes climate startup data from multiple sources."""

    def __init__(self, db: Database):
        self.db = db
        self.category_mapper = CategoryMapper()
        self.session: Optional[aiohttp.ClientSession] = None
        self.rate_limit_delay = 0.5  # seconds between requests

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def _fetch_url(self, url: str) -> Optional[str]:
        """Fetch URL content with retry logic."""
        if not self.session:
            raise RuntimeError("Scraper not initialized. Use async context manager.")

        await asyncio.sleep(self.rate_limit_delay)

        try:
            async with self.session.get(url, timeout=30) as response:
                if response.status == 200:
                    return await response.text()
                else:
                    logger.warning(f"HTTP {response.status} for {url}")
                    return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            raise

    async def scrape_yc_climate(self) -> List[Dict[str, Any]]:
        """Scrape Y Combinator climate companies from their directory."""
        logger.info("Scraping Y Combinator climate companies...")
        startups = []

        # YC company directory API endpoint for climate tagged companies
        base_url = "https://www.ycombinator.com/companies"

        try:
            html = await self._fetch_url(f"{base_url}?tags=Climate")
            if not html:
                return startups

            soup = BeautifulSoup(html, "lxml")

            # Find company cards
            company_cards = soup.select('a[class*="company"]')

            for card in company_cards[:500]:  # Limit to first 500
                try:
                    name_elem = card.select_one('span[class*="name"]')
                    desc_elem = card.select_one('span[class*="description"]')
                    location_elem = card.select_one('span[class*="location"]')

                    if not name_elem:
                        continue

                    name = name_elem.get_text(strip=True)
                    description = (
                        desc_elem.get_text(strip=True) if desc_elem else ""
                    )
                    location = (
                        location_elem.get_text(strip=True) if location_elem else ""
                    )

                    # Map to vertical
                    primary_vertical, secondary = self.category_mapper.map_startup(
                        name, description
                    )

                    startup = {
                        "name": name,
                        "short_description": description,
                        "headquarters_location": location,
                        "primary_vertical": primary_vertical,
                        "secondary_verticals": secondary,
                        "source": "yc",
                        "source_id": card.get("href", "").split("/")[-1],
                        "website_url": f"https://www.ycombinator.com{card.get('href', '')}",
                    }
                    startups.append(startup)
                except Exception as e:
                    logger.warning(f"Error parsing YC company card: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error scraping YC: {e}")

        logger.info(f"Scraped {len(startups)} companies from YC")
        return startups

    async def scrape_climatebase(self) -> List[Dict[str, Any]]:
        """Scrape companies from Climatebase."""
        logger.info("Scraping Climatebase companies...")
        startups = []

        try:
            # Climatebase company listings
            html = await self._fetch_url(
                "https://climatebase.org/companies?l=&q=&sector=&stage="
            )
            if not html:
                return startups

            soup = BeautifulSoup(html, "lxml")

            # Parse company data from script tags or list items
            company_items = soup.select('div[class*="company"]')

            for item in company_items[:500]:
                try:
                    name_elem = item.select_one('h3, [class*="name"]')
                    desc_elem = item.select_one('p, [class*="description"]')
                    link_elem = item.select_one("a")

                    if not name_elem:
                        continue

                    name = name_elem.get_text(strip=True)
                    description = (
                        desc_elem.get_text(strip=True) if desc_elem else ""
                    )
                    url = link_elem.get("href", "") if link_elem else ""

                    primary_vertical, secondary = self.category_mapper.map_startup(
                        name, description
                    )

                    startup = {
                        "name": name,
                        "short_description": description,
                        "primary_vertical": primary_vertical,
                        "secondary_verticals": secondary,
                        "source": "climatebase",
                        "website_url": url if url.startswith("http") else "",
                    }
                    startups.append(startup)
                except Exception as e:
                    logger.warning(f"Error parsing Climatebase company: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error scraping Climatebase: {e}")

        logger.info(f"Scraped {len(startups)} companies from Climatebase")
        return startups

    async def scrape_crunchbase_climate(self) -> List[Dict[str, Any]]:
        """
        Scrape climate companies from Crunchbase API.
        Requires API key for full access.
        """
        logger.info("Scraping Crunchbase climate companies...")
        startups = []

        api_key = settings.crunchbase_api_key
        if not api_key:
            logger.warning("No Crunchbase API key configured, skipping")
            return startups

        try:
            # Crunchbase API endpoint for climate companies
            base_url = "https://api.crunchbase.com/api/v4/searches/organizations"
            headers = {"X-cb-user-key": api_key}

            query = {
                "field_ids": [
                    "identifier",
                    "short_description",
                    "founded_on",
                    "funding_total",
                    "location_identifiers",
                    "website_url",
                    "linkedin",
                    "num_employees_enum",
                ],
                "query": [
                    {
                        "type": "predicate",
                        "field_id": "categories",
                        "operator_id": "includes",
                        "values": [
                            "clean-technology",
                            "renewable-energy",
                            "cleantech",
                            "sustainability",
                        ],
                    }
                ],
                "limit": 1000,
            }

            if self.session:
                async with self.session.post(
                    base_url, json=query, headers=headers
                ) as response:
                    if response.status == 200:
                        data = await response.json()

                        for entity in data.get("entities", []):
                            props = entity.get("properties", {})

                            name = props.get("identifier", {}).get("value", "")
                            description = props.get("short_description", "")

                            primary_vertical, secondary = (
                                self.category_mapper.map_startup(name, description)
                            )

                            # Parse funding
                            funding = props.get("funding_total", {})
                            funding_usd = funding.get("value_usd") if funding else None

                            # Parse founded year
                            founded = props.get("founded_on", {})
                            founded_year = None
                            if founded:
                                try:
                                    founded_year = int(founded.get("value", "")[:4])
                                except (ValueError, TypeError):
                                    pass

                            startup = {
                                "name": name,
                                "short_description": description,
                                "founded_year": founded_year,
                                "total_funding_usd": funding_usd,
                                "employee_count": props.get("num_employees_enum"),
                                "website_url": props.get("website_url"),
                                "linkedin_url": props.get("linkedin", {}).get("value"),
                                "primary_vertical": primary_vertical,
                                "secondary_verticals": secondary,
                                "source": "crunchbase",
                                "source_id": entity.get("uuid"),
                            }
                            startups.append(startup)
                    else:
                        logger.error(f"Crunchbase API error: {response.status}")

        except Exception as e:
            logger.error(f"Error scraping Crunchbase: {e}")

        logger.info(f"Scraped {len(startups)} companies from Crunchbase")
        return startups

    def generate_sample_data(self, count: int = 500) -> List[Dict[str, Any]]:
        """Generate sample climate startup data for development/testing."""
        import random

        logger.info(f"Generating {count} sample climate startups...")

        verticals = list(self.category_mapper.verticals.keys())

        sample_names = [
            "SolarFlow", "CarbonCapture Pro", "GridSync", "BatteryMax",
            "WindForce", "HydrogenGen", "EcoFarm", "CircularTech",
            "OceanBlue", "SteelGreen", "FloodGuard", "PowerGrid Plus",
            "SunHarvest", "AirClean", "WaterPure", "AgriSmart",
            "RecycleAI", "ClimateRisk", "EnergyStore", "GreenBuild",
        ]

        sample_descriptions = {
            "carbon_management": [
                "Direct air capture technology using novel sorbents",
                "Carbon sequestration through enhanced mineralization",
                "Biochar production for agricultural carbon removal",
                "Carbon credit marketplace and verification platform",
            ],
            "clean_energy": [
                "Next-generation solar panels with 30% higher efficiency",
                "Offshore wind turbine optimization using AI",
                "Perovskite solar cell manufacturing",
                "Community solar project development platform",
            ],
            "energy_storage": [
                "Grid-scale iron-air battery systems",
                "Solid-state lithium batteries for EVs",
                "Thermal energy storage using molten salt",
                "Second-life EV battery repurposing",
            ],
            "green_transportation": [
                "Electric aircraft for regional travel",
                "EV charging network with smart load balancing",
                "Sustainable aviation fuel from waste",
                "Electric ferry systems for urban waterways",
            ],
            "sustainable_agriculture": [
                "Vertical farming with 95% water savings",
                "Precision agriculture using satellite imagery",
                "Alternative protein from fermentation",
                "Regenerative agriculture soil monitoring",
            ],
            "built_environment": [
                "Smart HVAC systems reducing energy 40%",
                "Low-carbon concrete using industrial waste",
                "Building energy management platform",
                "Heat pump systems for commercial buildings",
            ],
            "circular_economy": [
                "Chemical recycling of mixed plastics",
                "Textile-to-textile recycling technology",
                "Electronics refurbishment marketplace",
                "Food waste to biofuel conversion",
            ],
            "climate_fintech": [
                "Carbon footprint tracking for businesses",
                "ESG data analytics platform",
                "Climate risk assessment for insurers",
                "Green bond verification and trading",
            ],
            "water_ocean": [
                "Solar-powered desalination systems",
                "Wastewater treatment using AI",
                "Seaweed farming for carbon credits",
                "Ocean plastic collection technology",
            ],
            "industrial_decarbonization": [
                "Green hydrogen electrolyzer manufacturing",
                "Electric arc furnace for steel production",
                "Industrial heat pump systems",
                "Ammonia production using renewables",
            ],
            "climate_adaptation": [
                "Wildfire detection using satellite AI",
                "Flood prediction and early warning",
                "Climate-resilient crop development",
                "Coastal protection infrastructure",
            ],
            "grid_energy_management": [
                "Virtual power plant software platform",
                "Demand response optimization",
                "Microgrid controller systems",
                "Grid-scale power electronics",
            ],
        }

        locations = [
            "San Francisco, CA", "Boston, MA", "New York, NY", "Austin, TX",
            "Seattle, WA", "Denver, CO", "Los Angeles, CA", "Chicago, IL",
            "London, UK", "Berlin, Germany", "Amsterdam, Netherlands",
            "Singapore", "Tel Aviv, Israel", "Toronto, Canada", "Sydney, Australia",
        ]

        funding_stages = ["Seed", "Series A", "Series B", "Series C", "Growth"]

        startups = []
        used_names = set()

        for i in range(count):
            vertical = random.choice(verticals)

            # Generate unique name
            base_name = random.choice(sample_names)
            name = f"{base_name} {random.choice(['AI', 'Tech', 'Systems', 'Solutions', 'Labs', 'Energy', ''])}"
            suffix = i // 20
            if suffix > 0:
                name = f"{name} {suffix}"

            while name in used_names:
                name = f"{name} {random.randint(1, 999)}"
            used_names.add(name)

            descriptions = sample_descriptions.get(vertical, ["Climate technology startup"])
            description = random.choice(descriptions)

            # Random funding (weighted toward lower amounts)
            funding = None
            if random.random() > 0.3:
                funding = random.choice([
                    random.randint(100000, 1000000),      # Seed
                    random.randint(1000000, 10000000),    # Series A
                    random.randint(10000000, 50000000),   # Series B
                    random.randint(50000000, 200000000),  # Series C+
                ])

            # Random year (weighted toward recent years)
            year = random.choices(
                range(2010, 2025),
                weights=[1, 1, 2, 2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 8, 5],
                k=1,
            )[0]

            startup = {
                "name": name.strip(),
                "short_description": description,
                "long_description": f"{description} We are focused on {self.category_mapper.get_vertical_name(vertical).lower()} solutions.",
                "founded_year": year,
                "total_funding_usd": funding,
                "funding_stage": random.choice(funding_stages) if funding else None,
                "employee_count": random.choice(["1-10", "11-50", "51-200", "201-500", "500+"]),
                "website_url": f"https://{name.lower().replace(' ', '')}.com",
                "headquarters_location": random.choice(locations),
                "country": random.choice(locations).split(", ")[-1],
                "primary_vertical": vertical,
                "secondary_verticals": random.sample(
                    [v for v in verticals if v != vertical], k=random.randint(0, 2)
                ),
                "technologies": self.category_mapper.extract_keywords(description),
                "keywords": self.category_mapper.verticals[vertical].get("keywords", [])[:5],
                "source": "sample",
                "source_id": f"sample_{i}",
            }
            startups.append(startup)

        logger.info(f"Generated {len(startups)} sample startups")
        return startups

    async def scrape_all_sources(self) -> int:
        """Scrape from all sources and save to database."""
        all_startups = []

        # Scrape from various sources
        yc_startups = await self.scrape_yc_climate()
        all_startups.extend(yc_startups)

        cb_startups = await self.scrape_climatebase()
        all_startups.extend(cb_startups)

        crunchbase_startups = await self.scrape_crunchbase_climate()
        all_startups.extend(crunchbase_startups)

        # If we didn't get enough real data, add sample data
        if len(all_startups) < 1000:
            sample_count = max(500, 1000 - len(all_startups))
            sample_startups = self.generate_sample_data(sample_count)
            all_startups.extend(sample_startups)

        # Save to database
        saved_count = 0
        for startup in all_startups:
            result = self.db.insert_startup(startup)
            if result:
                saved_count += 1

        logger.info(f"Saved {saved_count} startups to database")
        return saved_count
