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


class FirecrawlScraper:
    """Scrapes climate startup data using the Firecrawl API."""

    def __init__(self, db: Database, api_key: str):
        self.db = db
        self.api_key = api_key
        self.category_mapper = CategoryMapper()

    def _get_client(self):
        from firecrawl import FirecrawlApp
        return FirecrawlApp(api_key=self.api_key)

    def _extract_startups_from_markdown(self, markdown: str, source: str) -> List[Dict[str, Any]]:
        """Parse markdown text to extract company name/description pairs."""
        startups = []
        if not markdown:
            return startups

        # Split by lines to find company entries
        lines = markdown.split("\n")
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            # Look for headings or bold company names
            name = None
            desc = None

            # Match markdown headings like ## Company Name or ### Company Name
            heading_match = re.match(r"^#{1,4}\s+(.+)$", line)
            if heading_match:
                name = heading_match.group(1).strip().rstrip(".")
                # Next non-empty line(s) = description
                j = i + 1
                desc_parts = []
                while j < len(lines) and j < i + 5:
                    next_line = lines[j].strip()
                    if next_line and not next_line.startswith("#"):
                        # Remove markdown links but keep text
                        clean = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", next_line)
                        desc_parts.append(clean)
                        break
                    j += 1
                desc = " ".join(desc_parts)

            # Match **Company Name** patterns
            bold_match = re.match(r"^\*\*(.+?)\*\*[:\s\-–]*(.*)$", line)
            if bold_match and not heading_match:
                name = bold_match.group(1).strip()
                desc = bold_match.group(2).strip()
                if not desc and i + 1 < len(lines):
                    desc = lines[i + 1].strip()

            if name and len(name) > 2 and len(name) < 100:
                # Filter out navigation/UI elements
                skip_words = {"menu", "search", "login", "sign up", "home", "about",
                              "contact", "blog", "news", "jobs", "careers", "back",
                              "next", "previous", "more", "less", "view all", "see all"}
                if name.lower() not in skip_words:
                    primary_vertical, secondary = self.category_mapper.map_startup(name, desc or "")
                    if primary_vertical or source in ("yc_climate", "climatebase"):
                        startup = {
                            "name": name,
                            "short_description": desc[:500] if desc else "",
                            "primary_vertical": primary_vertical or "clean_energy",
                            "secondary_verticals": secondary,
                            "source": source,
                            "source_id": re.sub(r"[^a-z0-9]", "-", name.lower())[:50],
                        }
                        startups.append(startup)
            i += 1

        return startups

    def scrape_yc_climate(self) -> List[Dict[str, Any]]:
        """Scrape Y Combinator climate companies via Firecrawl extract."""
        logger.info("Scraping YC climate companies via Firecrawl...")
        startups = []
        try:
            app = self._get_client()
            # YC company search filtered to climate
            result = app.scrape_url(
                "https://www.ycombinator.com/companies?tags=Climate",
                formats=["extract"],
                actions=[{"type": "wait", "milliseconds": 2000}],
                extract={
                    "schema": {
                        "type": "object",
                        "properties": {
                            "companies": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "description": {"type": "string"},
                                        "location": {"type": "string"},
                                        "batch": {"type": "string"},
                                        "website": {"type": "string"},
                                    },
                                    "required": ["name"],
                                },
                            }
                        },
                        "required": ["companies"],
                    },
                    "prompt": "Extract all company names, descriptions, locations, YC batch (e.g. S22, W23), and website URLs from this page.",
                },
            )
            companies = []
            if hasattr(result, "extract") and result.extract:
                data = result.extract
                if isinstance(data, dict):
                    companies = data.get("companies", [])
            for company in companies:
                name = company.get("name", "").strip()
                if not name:
                    continue
                desc = company.get("description", "")
                primary_vertical, secondary = self.category_mapper.map_startup(name, desc)
                startup = {
                    "name": name,
                    "short_description": desc[:500],
                    "headquarters_location": company.get("location", ""),
                    "website_url": company.get("website", ""),
                    "primary_vertical": primary_vertical or "clean_energy",
                    "secondary_verticals": secondary,
                    "source": "yc",
                    "source_id": re.sub(r"[^a-z0-9]", "-", name.lower())[:50],
                }
                startups.append(startup)
            logger.info(f"Scraped {len(startups)} YC climate companies")
        except Exception as e:
            logger.error(f"Error scraping YC via Firecrawl: {e}")
        return startups

    def scrape_climatebase(self) -> List[Dict[str, Any]]:
        """Scrape Climatebase companies via Firecrawl."""
        logger.info("Scraping Climatebase via Firecrawl...")
        startups = []
        try:
            app = self._get_client()
            result = app.scrape_url(
                "https://climatebase.org/companies",
                formats=["extract"],
                actions=[{"type": "wait", "milliseconds": 2000}],
                extract={
                    "schema": {
                        "type": "object",
                        "properties": {
                            "companies": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "description": {"type": "string"},
                                        "sector": {"type": "string"},
                                        "location": {"type": "string"},
                                        "website": {"type": "string"},
                                        "employee_count": {"type": "string"},
                                    },
                                    "required": ["name"],
                                },
                            }
                        },
                        "required": ["companies"],
                    },
                    "prompt": "Extract all company names, descriptions, sectors, locations, website URLs, and employee counts from this climate company directory.",
                },
            )
            companies = []
            if hasattr(result, "extract") and result.extract:
                data = result.extract
                if isinstance(data, dict):
                    companies = data.get("companies", [])
            for company in companies:
                name = company.get("name", "").strip()
                if not name:
                    continue
                desc = company.get("description", "")
                primary_vertical, secondary = self.category_mapper.map_startup(
                    name, f"{desc} {company.get('sector', '')}"
                )
                startup = {
                    "name": name,
                    "short_description": desc[:500],
                    "headquarters_location": company.get("location", ""),
                    "website_url": company.get("website", ""),
                    "employee_count": company.get("employee_count", ""),
                    "primary_vertical": primary_vertical or "clean_energy",
                    "secondary_verticals": secondary,
                    "source": "climatebase",
                    "source_id": re.sub(r"[^a-z0-9]", "-", name.lower())[:50],
                }
                startups.append(startup)
            logger.info(f"Scraped {len(startups)} Climatebase companies")
        except Exception as e:
            logger.error(f"Error scraping Climatebase via Firecrawl: {e}")
        return startups

    def _scrape_vc_portfolio(self, url: str, source_name: str) -> List[Dict[str, Any]]:
        """Generic VC portfolio scraper using Firecrawl extract."""
        startups = []
        try:
            app = self._get_client()
            result = app.scrape_url(
                url,
                formats=["extract"],
                extract={
                    "schema": {
                        "type": "object",
                        "properties": {
                            "companies": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "description": {"type": "string"},
                                        "website": {"type": "string"},
                                        "sector": {"type": "string"},
                                    },
                                    "required": ["name"],
                                },
                            }
                        },
                        "required": ["companies"],
                    },
                    "prompt": f"Extract all portfolio company names, descriptions, websites, and sectors from this venture capital portfolio page.",
                },
            )
            companies = []
            if hasattr(result, "extract") and result.extract:
                data = result.extract
                if isinstance(data, dict):
                    companies = data.get("companies", [])
            for company in companies:
                name = company.get("name", "").strip()
                if not name:
                    continue
                desc = company.get("description", "")
                primary_vertical, secondary = self.category_mapper.map_startup(
                    name, f"{desc} {company.get('sector', '')}"
                )
                startup = {
                    "name": name,
                    "short_description": desc[:500],
                    "website_url": company.get("website", ""),
                    "primary_vertical": primary_vertical or "clean_energy",
                    "secondary_verticals": secondary,
                    "source": source_name,
                    "source_id": re.sub(r"[^a-z0-9]", "-", name.lower())[:50],
                }
                startups.append(startup)
            logger.info(f"Scraped {len(startups)} companies from {source_name}")
        except Exception as e:
            logger.error(f"Error scraping {source_name} via Firecrawl: {e}")
        return startups

    def scrape_all_vc_portfolios(self) -> List[Dict[str, Any]]:
        """Scrape multiple climate VC portfolio pages."""
        all_startups = []

        vc_sources = [
            ("https://www.lowercarbon.com/portfolio", "lowercarbon"),
            ("https://mcjcollective.com/our-work/portfolio", "mcj_collective"),
            ("https://congruentvc.com/portfolio/", "congruent_vc"),
            ("https://breakthrough.energy/program/breakthrough-energy-ventures/", "breakthrough_energy"),
            ("https://www.energy-impact.com/portfolio/", "energy_impact"),
            ("https://earthshot.eco/portfolio/", "earthshot"),
        ]

        for url, source_name in vc_sources:
            try:
                logger.info(f"Scraping {source_name}...")
                companies = self._scrape_vc_portfolio(url, source_name)
                all_startups.extend(companies)
                # Small delay between requests
                import time
                time.sleep(1)
            except Exception as e:
                logger.warning(f"Failed to scrape {source_name}: {e}")

        return all_startups

    def scrape_all_sources(self) -> int:
        """Scrape all sources and save to database."""
        all_startups = []

        # YC Climate companies
        try:
            yc = self.scrape_yc_climate()
            all_startups.extend(yc)
        except Exception as e:
            logger.error(f"YC scraping failed: {e}")

        # Climatebase
        try:
            cb = self.scrape_climatebase()
            all_startups.extend(cb)
        except Exception as e:
            logger.error(f"Climatebase scraping failed: {e}")

        # VC portfolios
        try:
            vc = self.scrape_all_vc_portfolios()
            all_startups.extend(vc)
        except Exception as e:
            logger.error(f"VC portfolio scraping failed: {e}")

        # Deduplicate by name
        seen_names = set()
        unique_startups = []
        for s in all_startups:
            key = s["name"].lower().strip()
            if key not in seen_names:
                seen_names.add(key)
                unique_startups.append(s)

        # Save to database
        saved = 0
        for startup in unique_startups:
            result = self.db.insert_startup(startup)
            if result:
                saved += 1

        logger.info(f"Saved {saved} unique startups from Firecrawl sources")
        return saved


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
        """Load Y Combinator climate companies — expanded curated list."""
        logger.info("Loading Y Combinator climate companies...")

        yc_climate_companies = [
            # Energy
            {"name": "Oklo", "description": "Advanced fission power plants for emission-free always-on power", "location": "Santa Clara, CA", "vertical": "clean_energy"},
            {"name": "Commonwealth Fusion Systems", "description": "Compact fusion energy using high-temperature superconducting magnets", "location": "Cambridge, MA", "vertical": "clean_energy"},
            {"name": "Heliogen", "description": "AI-powered concentrated solar energy for industrial heat", "location": "Pasadena, CA", "vertical": "clean_energy"},
            {"name": "Sunrun", "description": "Residential solar and battery storage systems", "location": "San Francisco, CA", "vertical": "clean_energy"},
            {"name": "Palmetto Clean Technology", "description": "Platform for residential clean energy adoption", "location": "Charlotte, NC", "vertical": "clean_energy"},
            # Carbon
            {"name": "Heirloom Carbon", "description": "Direct air capture using enhanced rock weathering", "location": "San Francisco, CA", "vertical": "carbon_management"},
            {"name": "Charm Industrial", "description": "Bio-oil injection for permanent carbon removal", "location": "San Francisco, CA", "vertical": "carbon_management"},
            {"name": "Pachama", "description": "AI platform to verify forest carbon credits", "location": "San Francisco, CA", "vertical": "carbon_management"},
            {"name": "Terraset", "description": "Carbon removal marketplace for businesses", "location": "San Francisco, CA", "vertical": "carbon_management"},
            {"name": "Sustaera", "description": "Direct air capture using monolith sorbents", "location": "Chapel Hill, NC", "vertical": "carbon_management"},
            # Storage
            {"name": "Form Energy", "description": "Iron-air batteries for multi-day grid-scale energy storage", "location": "Somerville, MA", "vertical": "energy_storage"},
            {"name": "Ambri", "description": "Liquid metal batteries for long-duration grid storage", "location": "Marlborough, MA", "vertical": "energy_storage"},
            {"name": "Noon Energy", "description": "Carbon-oxygen batteries for long-duration storage", "location": "Menlo Park, CA", "vertical": "energy_storage"},
            {"name": "Ascend Elements", "description": "Battery materials from recycled lithium-ion batteries", "location": "Westborough, MA", "vertical": "energy_storage"},
            # Transportation
            {"name": "Joby Aviation", "description": "Electric air taxi for urban mobility", "location": "Santa Cruz, CA", "vertical": "green_transportation"},
            {"name": "Lilium", "description": "Electric vertical takeoff and landing jets", "location": "Munich, Germany", "vertical": "green_transportation"},
            {"name": "Arcimoto", "description": "Electric vehicles for everyday trips", "location": "Eugene, OR", "vertical": "green_transportation"},
            {"name": "Volta Industries", "description": "EV charging network at retail locations", "location": "San Francisco, CA", "vertical": "green_transportation"},
            {"name": "Einride", "description": "Autonomous and electric freight transport", "location": "Stockholm, Sweden", "vertical": "green_transportation"},
            # Agriculture
            {"name": "Pivot Bio", "description": "Microbial nitrogen for corn replacing synthetic fertilizer", "location": "Berkeley, CA", "vertical": "sustainable_agriculture"},
            {"name": "Apeel Sciences", "description": "Plant-based coatings to extend produce shelf life", "location": "Goleta, CA", "vertical": "sustainable_agriculture"},
            {"name": "Bowery Farming", "description": "Indoor vertical farming with zero pesticides", "location": "New York, NY", "vertical": "sustainable_agriculture"},
            {"name": "Sound Agriculture", "description": "Nutrient efficiency products for crop yields", "location": "Emeryville, CA", "vertical": "sustainable_agriculture"},
            {"name": "Plenty", "description": "Indoor vertical farming using AI and robotics", "location": "San Francisco, CA", "vertical": "sustainable_agriculture"},
            # Built Environment
            {"name": "BlocPower", "description": "Green retrofit financing for urban buildings", "location": "New York, NY", "vertical": "built_environment"},
            {"name": "Turntide Technologies", "description": "Smart motor systems to cut building energy use", "location": "San Jose, CA", "vertical": "built_environment"},
            {"name": "Dandelion Energy", "description": "Home geothermal heating and cooling systems", "location": "Mount Kisco, NY", "vertical": "built_environment"},
            {"name": "Sealed", "description": "Whole-home energy efficiency upgrade financing", "location": "New York, NY", "vertical": "built_environment"},
            {"name": "Pearl Certification", "description": "Green home certification for energy features", "location": "Charlottesville, VA", "vertical": "built_environment"},
            # Circular Economy
            {"name": "Ginkgo Bioworks", "description": "Cell programming platform for biological products", "location": "Boston, MA", "vertical": "circular_economy"},
            {"name": "Novamont", "description": "Bioplastics and bioproducts from renewable resources", "location": "Novara, Italy", "vertical": "circular_economy"},
            {"name": "Solugen", "description": "Carbon-negative chemistry using bioengineered enzymes", "location": "Houston, TX", "vertical": "circular_economy"},
            {"name": "Nth Cycle", "description": "Critical mineral recycling from e-waste", "location": "Boston, MA", "vertical": "circular_economy"},
            # Climate Fintech
            {"name": "Watershed", "description": "Enterprise carbon management and reporting platform", "location": "San Francisco, CA", "vertical": "climate_fintech"},
            {"name": "Rubicon Carbon", "description": "Carbon credit portfolio management for enterprises", "location": "New York, NY", "vertical": "climate_fintech"},
            {"name": "Persefoni", "description": "Climate management and accounting platform", "location": "Scottsdale, AZ", "vertical": "climate_fintech"},
            {"name": "Xpansiv", "description": "Market infrastructure for environmental commodities", "location": "San Francisco, CA", "vertical": "climate_fintech"},
            # Water
            {"name": "Energy Recovery", "description": "Energy recovery devices for water desalination", "location": "San Leandro, CA", "vertical": "water_ocean"},
            {"name": "Gradiant", "description": "Water treatment technology for industrial wastewater", "location": "Boston, MA", "vertical": "water_ocean"},
            {"name": "Aquacycl", "description": "Wastewater treatment using bioelectrochemical systems", "location": "San Diego, CA", "vertical": "water_ocean"},
            # Industrial Decarbonization
            {"name": "Boston Metal", "description": "Green steel production using molten oxide electrolysis", "location": "Woburn, MA", "vertical": "industrial_decarbonization"},
            {"name": "Electra Steel", "description": "Low-temperature iron production using electricity", "location": "Boulder, CO", "vertical": "industrial_decarbonization"},
            {"name": "Sublime Systems", "description": "Electrochemical cement production replacing kilns", "location": "Somerville, MA", "vertical": "industrial_decarbonization"},
            {"name": "Twelve", "description": "CO2 conversion to chemicals and fuels using electrolysis", "location": "Berkeley, CA", "vertical": "industrial_decarbonization"},
            # Climate Adaptation
            {"name": "Jupiter Intelligence", "description": "Climate risk analytics for infrastructure and finance", "location": "San Mateo, CA", "vertical": "climate_adaptation"},
            {"name": "Kettle", "description": "Reinsurance for wildfire using ML risk modeling", "location": "San Francisco, CA", "vertical": "climate_adaptation"},
            {"name": "One Concern", "description": "Disaster resilience analytics using AI", "location": "Palo Alto, CA", "vertical": "climate_adaptation"},
            # Grid Management
            {"name": "AutoGrid", "description": "AI-powered energy flexibility management platform", "location": "Redwood City, CA", "vertical": "grid_energy_management"},
            {"name": "Leap", "description": "Virtual power plant network aggregating distributed energy", "location": "San Francisco, CA", "vertical": "grid_energy_management"},
            {"name": "Enbala Power Networks", "description": "Distributed energy resource optimization platform", "location": "Vancouver, BC", "vertical": "grid_energy_management"},
        ]

        startups = []
        for company in yc_climate_companies:
            primary_vertical, secondary = self.category_mapper.map_startup(
                company["name"], company["description"]
            )
            if not primary_vertical:
                primary_vertical = company.get("vertical", "clean_energy")

            startup = {
                "name": company["name"],
                "short_description": company["description"],
                "headquarters_location": company.get("location", ""),
                "primary_vertical": primary_vertical,
                "secondary_verticals": secondary,
                "source": "yc",
                "source_id": re.sub(r"[^a-z0-9]", "-", company["name"].lower())[:50],
                "website_url": f"https://www.ycombinator.com/companies/{company['name'].lower().replace(' ', '-')}",
            }
            startups.append(startup)

        logger.info(f"Loaded {len(startups)} YC climate companies")
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

            funding = None
            if random.random() > 0.3:
                funding = random.choice([
                    random.randint(100000, 1000000),
                    random.randint(1000000, 10000000),
                    random.randint(10000000, 50000000),
                    random.randint(50000000, 200000000),
                ])

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
        """Scrape from all sources. Uses Firecrawl if API key is available, else curated list."""
        all_startups = []

        # Check for Firecrawl API key
        firecrawl_key = getattr(settings, "firecrawl_api_key", "") or ""

        if firecrawl_key:
            logger.info("Firecrawl API key found — using Firecrawl for comprehensive scraping")
            try:
                fc_scraper = FirecrawlScraper(self.db, firecrawl_key)
                saved = fc_scraper.scrape_all_sources()
                logger.info(f"Firecrawl scraping complete: {saved} startups saved")
                return saved
            except Exception as e:
                logger.error(f"Firecrawl scraping failed, falling back to curated list: {e}")

        # Fallback: curated YC list
        logger.info("Using curated YC climate company list...")
        yc_startups = await self.scrape_yc_climate()
        all_startups.extend(yc_startups)

        saved_count = 0
        for startup in all_startups:
            result = self.db.insert_startup(startup)
            if result:
                saved_count += 1

        logger.info(f"Saved {saved_count} startups to database")
        return saved_count
