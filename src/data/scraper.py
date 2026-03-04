"""Web scrapers for climate startup data from various sources."""

import asyncio
import logging
import re
import time
from typing import List, Dict, Any, Optional

import aiohttp
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

    def _extract_companies(self, result) -> List[Dict[str, Any]]:
        """Pull companies list from a Firecrawl extract result."""
        companies = []
        if hasattr(result, "extract") and result.extract:
            data = result.extract
            if isinstance(data, dict):
                companies = data.get("companies", [])
        return companies

    def _build_startup(self, company: Dict, source: str) -> Optional[Dict[str, Any]]:
        """Convert a raw company dict into a startup record."""
        name = company.get("name", "").strip()
        if not name or len(name) < 2:
            return None
        desc = company.get("description", "") or ""
        sector = company.get("sector", "") or ""
        primary_vertical, secondary = self.category_mapper.map_startup(
            name, f"{desc} {sector}"
        )
        slug = re.sub(r"[^a-z0-9]", "-", name.lower())[:50]
        yc_url = f"https://www.ycombinator.com/companies/{slug}" if source == "yc" else None
        return {
            "name": name,
            "short_description": desc[:500],
            "headquarters_location": company.get("location", "") or "",
            "website_url": company.get("website", "") or "",
            "yc_url": yc_url,
            "employee_count": company.get("employee_count", "") or "",
            "founded_year": company.get("founded_year") or None,
            "total_funding_usd": company.get("total_funding_usd") or None,
            "funding_stage": company.get("funding_stage", "") or "",
            "primary_vertical": primary_vertical or "clean_energy",
            "secondary_verticals": secondary,
            "source": source,
            "source_id": slug,
        }

    _COMPANY_SCHEMA = {
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
                        "website": {"type": "string"},
                        "sector": {"type": "string"},
                        "employee_count": {"type": "string"},
                        "founded_year": {"type": "integer"},
                        "funding_stage": {"type": "string"},
                    },
                    "required": ["name"],
                },
            }
        },
        "required": ["companies"],
    }

    def scrape_yc_climate(self) -> List[Dict[str, Any]]:
        """Scrape Y Combinator climate companies via Firecrawl."""
        logger.info("Scraping YC climate companies via Firecrawl...")
        startups = []
        try:
            app = self._get_client()
            result = app.scrape_url(
                "https://www.ycombinator.com/companies?tags=Climate",
                formats=["extract"],
                actions=[{"type": "wait", "milliseconds": 3000}],
                extract={
                    "schema": self._COMPANY_SCHEMA,
                    "prompt": (
                        "Extract ALL company names, one-line descriptions, locations, "
                        "and website URLs from this YC company listing page. "
                        "Include every company shown, do not truncate."
                    ),
                },
            )
            for company in self._extract_companies(result):
                startup = self._build_startup(company, "yc")
                if startup:
                    startups.append(startup)
            logger.info(f"Scraped {len(startups)} YC climate companies")
        except Exception as e:
            logger.error(f"Error scraping YC via Firecrawl: {e}")
        return startups

    def scrape_climatebase(self) -> List[Dict[str, Any]]:
        """Scrape Climatebase companies via Firecrawl (multiple pages)."""
        logger.info("Scraping Climatebase via Firecrawl...")
        startups = []
        try:
            app = self._get_client()
            # Try crawling multiple pages of the company directory
            urls = [
                "https://climatebase.org/companies",
                "https://climatebase.org/companies?page=2",
                "https://climatebase.org/companies?page=3",
            ]
            for url in urls:
                try:
                    result = app.scrape_url(
                        url,
                        formats=["extract"],
                        actions=[{"type": "wait", "milliseconds": 2000}],
                        extract={
                            "schema": self._COMPANY_SCHEMA,
                            "prompt": (
                                "Extract all company names, descriptions, sectors, "
                                "locations, and website URLs from this climate company directory. "
                                "Include every company shown."
                            ),
                        },
                    )
                    for company in self._extract_companies(result):
                        startup = self._build_startup(company, "climatebase")
                        if startup:
                            startups.append(startup)
                    time.sleep(1)
                except Exception as e:
                    logger.warning(f"Error scraping {url}: {e}")
                    break
            logger.info(f"Scraped {len(startups)} Climatebase companies")
        except Exception as e:
            logger.error(f"Error scraping Climatebase via Firecrawl: {e}")
        return startups

    def scrape_ctvc(self) -> List[Dict[str, Any]]:
        """Scrape CTVC (Climate Tech VC) portfolio."""
        logger.info("Scraping CTVC portfolio...")
        return self._scrape_vc_portfolio(
            "https://www.ctvc.co/portfolio/",
            "ctvc",
            "Extract all portfolio company names, descriptions, and websites from this climate tech VC portfolio.",
        )

    def _scrape_vc_portfolio(self, url: str, source_name: str, prompt: str = None) -> List[Dict[str, Any]]:
        """Generic VC portfolio scraper using Firecrawl extract."""
        startups = []
        try:
            app = self._get_client()
            result = app.scrape_url(
                url,
                formats=["extract"],
                extract={
                    "schema": self._COMPANY_SCHEMA,
                    "prompt": prompt or (
                        "Extract all portfolio company names, descriptions, websites, "
                        "and sectors from this venture capital portfolio page."
                    ),
                },
            )
            for company in self._extract_companies(result):
                startup = self._build_startup(company, source_name)
                if startup:
                    startups.append(startup)
            logger.info(f"Scraped {len(startups)} companies from {source_name}")
        except Exception as e:
            logger.error(f"Error scraping {source_name} via Firecrawl: {e}")
        return startups

    def scrape_all_vc_portfolios(self) -> List[Dict[str, Any]]:
        """Scrape multiple climate VC portfolio pages."""
        all_startups = []

        vc_sources = [
            ("https://www.lowercarbon.com/portfolio", "lowercarbon",
             "Extract all portfolio company names and descriptions from LowerCarbon Capital's climate investment portfolio."),
            ("https://mcjcollective.com/our-work/portfolio", "mcj_collective",
             "Extract all portfolio company names, descriptions, and websites."),
            ("https://congruentvc.com/portfolio/", "congruent_vc",
             "Extract all portfolio company names, descriptions, and websites."),
            ("https://breakthrough.energy/program/breakthrough-energy-ventures/", "breakthrough_energy",
             "Extract all portfolio company names and descriptions from Breakthrough Energy Ventures portfolio."),
            ("https://www.energy-impact.com/portfolio/", "energy_impact",
             "Extract all portfolio company names, descriptions, and websites from Energy Impact Partners portfolio."),
            ("https://earthshot.eco/portfolio/", "earthshot",
             "Extract all portfolio company names and descriptions."),
            ("https://www.ctvc.co/portfolio/", "ctvc",
             "Extract all portfolio company names and descriptions from this climate tech VC portfolio."),
            ("https://greentown.com/companies/", "greentown_labs",
             "Extract all member company names, descriptions, and websites from Greentown Labs."),
            ("https://climatehaven.org/companies/", "climate_haven",
             "Extract all company names and descriptions from Climate Haven portfolio."),
            ("https://www.plantbasedfunds.com/portfolio", "plant_based_funds",
             "Extract all portfolio company names and descriptions."),
            ("https://investindiversity.com/portfolio", "invest_diversity",
             "Extract all portfolio company names and descriptions."),
        ]

        for url, source_name, prompt in vc_sources:
            try:
                logger.info(f"Scraping {source_name}...")
                companies = self._scrape_vc_portfolio(url, source_name, prompt)
                all_startups.extend(companies)
                time.sleep(1)
            except Exception as e:
                logger.warning(f"Failed to scrape {source_name}: {e}")

        return all_startups

    def scrape_all_sources(self) -> int:
        """Scrape all sources and save to database."""
        all_startups = []

        for scrape_fn, label in [
            (self.scrape_yc_climate, "YC Climate"),
            (self.scrape_climatebase, "Climatebase"),
            (self.scrape_all_vc_portfolios, "VC Portfolios"),
        ]:
            try:
                results = scrape_fn()
                all_startups.extend(results)
                logger.info(f"{label}: {len(results)} companies")
            except Exception as e:
                logger.error(f"{label} scraping failed: {e}")

        # Deduplicate by name
        seen = set()
        unique = []
        for s in all_startups:
            key = s["name"].lower().strip()
            if key not in seen:
                seen.add(key)
                unique.append(s)

        saved = sum(1 for s in unique if self.db.insert_startup(s))
        logger.info(f"Saved {saved} unique startups from Firecrawl sources")
        return saved


class ClimateScraper:
    """Scrapes climate startup data from multiple sources."""

    def __init__(self, db: Database):
        self.db = db
        self.category_mapper = CategoryMapper()
        self.session: Optional[aiohttp.ClientSession] = None

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
        await asyncio.sleep(0.5)
        try:
            async with self.session.get(url, timeout=30) as response:
                if response.status == 200:
                    return await response.text()
                logger.warning(f"HTTP {response.status} for {url}")
                return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            raise

    async def scrape_yc_climate(self) -> List[Dict[str, Any]]:
        """Load an expanded curated list of real climate startups."""
        logger.info("Loading curated climate startup list...")

        companies = [
            # ── Clean Energy ───────────────────────────────────────────────────────
            {"name": "Oklo", "description": "Advanced fission power plants for emission-free always-on power", "location": "Santa Clara, CA", "vertical": "clean_energy", "year": 2013},
            {"name": "Commonwealth Fusion Systems", "description": "Compact fusion energy using high-temperature superconducting magnets", "location": "Cambridge, MA", "vertical": "clean_energy", "year": 2018},
            {"name": "Heliogen", "description": "AI-powered concentrated solar energy for industrial heat and power", "location": "Pasadena, CA", "vertical": "clean_energy", "year": 2013},
            {"name": "Sunrun", "description": "Residential solar and battery storage subscription service", "location": "San Francisco, CA", "vertical": "clean_energy", "year": 2007},
            {"name": "Palmetto Clean Technology", "description": "Platform connecting homeowners to solar installers and clean energy financing", "location": "Charlotte, NC", "vertical": "clean_energy", "year": 2010},
            {"name": "Nextracker", "description": "Intelligent solar tracker systems that follow the sun to maximize output", "location": "Fremont, CA", "vertical": "clean_energy", "year": 2013},
            {"name": "Array Technologies", "description": "Solar tracking systems for utility-scale solar installations", "location": "Albuquerque, NM", "vertical": "clean_energy", "year": 1989},
            {"name": "Xcel Energy", "description": "Utility company transitioning to 100% carbon-free electricity by 2050", "location": "Minneapolis, MN", "vertical": "clean_energy", "year": 1909},
            {"name": "Lightpath Technologies", "description": "High-efficiency optical components for solar concentrators", "location": "Orlando, FL", "vertical": "clean_energy", "year": 1992},
            {"name": "Rondo Energy", "description": "Heat batteries storing renewable electricity as industrial heat", "location": "San Francisco, CA", "vertical": "clean_energy", "year": 2020},
            {"name": "Helion Energy", "description": "Fusion energy company targeting commercial electricity production by 2028", "location": "Everett, WA", "vertical": "clean_energy", "year": 2013},
            {"name": "TAE Technologies", "description": "Clean fusion energy using field-reversed configuration plasma", "location": "Foothill Ranch, CA", "vertical": "clean_energy", "year": 1998},
            {"name": "Zap Energy", "description": "Shear-flow stabilized z-pinch fusion energy", "location": "Seattle, WA", "vertical": "clean_energy", "year": 2017},
            {"name": "Orca Solar", "description": "Perovskite-silicon tandem solar cells with >30% efficiency", "location": "San Jose, CA", "vertical": "clean_energy", "year": 2021},
            {"name": "Swift Solar", "description": "Perovskite solar module manufacturing for lower-cost solar", "location": "San Carlos, CA", "vertical": "clean_energy", "year": 2017},
            {"name": "Yellow Door Energy", "description": "Solar energy solutions for commercial and industrial businesses in MENA", "location": "Dubai, UAE", "vertical": "clean_energy", "year": 2015},
            {"name": "SunPower", "description": "High-efficiency solar panels and energy storage for homes and businesses", "location": "San Jose, CA", "vertical": "clean_energy", "year": 1985},
            {"name": "First Solar", "description": "Thin-film CdTe solar panels for utility-scale power plants", "location": "Tempe, AZ", "vertical": "clean_energy", "year": 1999},

            # ── Carbon Management ──────────────────────────────────────────────────
            {"name": "Heirloom Carbon", "description": "Direct air capture using enhanced rock weathering with limestone", "location": "San Francisco, CA", "vertical": "carbon_management", "year": 2020},
            {"name": "Charm Industrial", "description": "Bio-oil injection for permanent carbon removal at scale", "location": "San Francisco, CA", "vertical": "carbon_management", "year": 2018},
            {"name": "Pachama", "description": "AI platform to verify and sell forest carbon credits with satellite monitoring", "location": "San Francisco, CA", "vertical": "carbon_management", "year": 2018},
            {"name": "Sustaera", "description": "Modular direct air capture using monolith ceramic sorbents", "location": "Chapel Hill, NC", "vertical": "carbon_management", "year": 2020},
            {"name": "Verdox", "description": "Electrochemical carbon capture for industrial flue gas at low cost", "location": "Boston, MA", "vertical": "carbon_management", "year": 2019},
            {"name": "CarbonCapture", "description": "Modular direct air capture machines deployable anywhere", "location": "Los Angeles, CA", "vertical": "carbon_management", "year": 2019},
            {"name": "Running Tide", "description": "Ocean-based carbon removal using kelp and biomass sinking", "location": "Portland, ME", "vertical": "carbon_management", "year": 2019},
            {"name": "Carbfix", "description": "Permanent CO2 mineralization in basalt rock underground", "location": "Reykjavik, Iceland", "vertical": "carbon_management", "year": 2007},
            {"name": "Climeworks", "description": "Direct air capture plants that remove CO2 from the atmosphere", "location": "Zurich, Switzerland", "vertical": "carbon_management", "year": 2009},
            {"name": "Carbon Engineering", "description": "Industrial-scale direct air capture technology acquired by Occidental", "location": "Squamish, BC", "vertical": "carbon_management", "year": 2009},
            {"name": "Global Thermostat", "description": "Direct air capture using solid sorbent materials and waste heat", "location": "New York, NY", "vertical": "carbon_management", "year": 2010},
            {"name": "Puro.earth", "description": "Carbon removal marketplace for biochar, wood burial, and other CDR", "location": "Helsinki, Finland", "vertical": "carbon_management", "year": 2018},
            {"name": "Anew Climate", "description": "Full-service carbon and environmental asset management platform", "location": "Denver, CO", "vertical": "carbon_management", "year": 2022},
            {"name": "South Pole", "description": "Global carbon project developer and climate solutions provider", "location": "Zurich, Switzerland", "vertical": "carbon_management", "year": 2011},
            {"name": "3Degrees", "description": "Renewable energy and carbon offset project development for corporates", "location": "San Francisco, CA", "vertical": "carbon_management", "year": 2002},
            {"name": "Verra", "description": "Standards organization for high-quality carbon and sustainability credits", "location": "Washington, DC", "vertical": "carbon_management", "year": 2005},
            {"name": "Gold Standard", "description": "Certification body for carbon offsets and sustainable development impacts", "location": "Geneva, Switzerland", "vertical": "carbon_management", "year": 2003},
            {"name": "Terraset", "description": "Carbon removal marketplace connecting businesses to verified CDR projects", "location": "San Francisco, CA", "vertical": "carbon_management", "year": 2021},
            {"name": "Loam Bio", "description": "Fungal seed coatings that increase soil carbon sequestration in farmland", "location": "Orange, Australia", "vertical": "carbon_management", "year": 2019},
            {"name": "Inplanet", "description": "Enhanced rock weathering for carbon removal and soil improvement", "location": "Munich, Germany", "vertical": "carbon_management", "year": 2021},
            {"name": "UNDO Carbon", "description": "Enhanced rock weathering spreading basalt on agricultural fields", "location": "London, UK", "vertical": "carbon_management", "year": 2021},
            {"name": "Eion Carbon", "description": "Enhanced weathering carbon removal through olivine-based soil amendments", "location": "New York, NY", "vertical": "carbon_management", "year": 2022},

            # ── Energy Storage ─────────────────────────────────────────────────────
            {"name": "Form Energy", "description": "Iron-air batteries enabling multi-day grid-scale energy storage", "location": "Somerville, MA", "vertical": "energy_storage", "year": 2017},
            {"name": "Ambri", "description": "Liquid metal batteries for long-duration utility-scale grid storage", "location": "Marlborough, MA", "vertical": "energy_storage", "year": 2010},
            {"name": "Noon Energy", "description": "Carbon-oxygen batteries for long-duration energy storage", "location": "Menlo Park, CA", "vertical": "energy_storage", "year": 2019},
            {"name": "Ascend Elements", "description": "Hydro-to-Cathode battery materials from recycled lithium-ion batteries", "location": "Westborough, MA", "vertical": "energy_storage", "year": 2015},
            {"name": "QuantumScape", "description": "Solid-state lithium-metal batteries for electric vehicles", "location": "San Jose, CA", "vertical": "energy_storage", "year": 2010},
            {"name": "Solid Power", "description": "All-solid-state battery cells for next-generation EVs", "location": "Louisville, CO", "vertical": "energy_storage", "year": 2012},
            {"name": "Eos Energy", "description": "Zinc-based batteries for safe, long-duration grid storage", "location": "Edison, NJ", "vertical": "energy_storage", "year": 2008},
            {"name": "ESS Tech", "description": "All-iron flow batteries for multi-hour grid-scale energy storage", "location": "Wilsonville, OR", "vertical": "energy_storage", "year": 2011},
            {"name": "Invinity Energy Systems", "description": "Vanadium flow batteries for commercial and utility energy storage", "location": "Edinburgh, UK", "vertical": "energy_storage", "year": 2019},
            {"name": "Malta", "description": "Pumped heat electricity storage using molten salt and cold antifreeze", "location": "Cambridge, MA", "vertical": "energy_storage", "year": 2018},
            {"name": "EnerVault", "description": "Iron-chromium redox flow batteries for long-duration storage", "location": "Sunnyvale, CA", "vertical": "energy_storage", "year": 2011},
            {"name": "Li-Cycle", "description": "Lithium-ion battery recycling for recovery of critical materials", "location": "Toronto, Canada", "vertical": "energy_storage", "year": 2016},
            {"name": "Redwood Materials", "description": "Battery recycling and materials refining for circular supply chains", "location": "Carson City, NV", "vertical": "energy_storage", "year": 2017},
            {"name": "Altris", "description": "Sodium-ion batteries using Prussian blue cathode for low-cost storage", "location": "Uppsala, Sweden", "vertical": "energy_storage", "year": 2017},
            {"name": "Natron Energy", "description": "Prussian blue sodium-ion batteries for industrial UPS and data centers", "location": "Santa Clara, CA", "vertical": "energy_storage", "year": 2012},
            {"name": "Energy Dome", "description": "CO2 battery for long-duration grid storage using compressed gas", "location": "Milan, Italy", "vertical": "energy_storage", "year": 2019},
            {"name": "Gravitricity", "description": "Gravity-based energy storage using heavy weights in mine shafts", "location": "Edinburgh, UK", "vertical": "energy_storage", "year": 2018},
            {"name": "Highview Power", "description": "Liquid air energy storage for long-duration grid applications", "location": "London, UK", "vertical": "energy_storage", "year": 2005},

            # ── Green Transportation ───────────────────────────────────────────────
            {"name": "Joby Aviation", "description": "Electric air taxi VTOL aircraft for quiet urban air mobility", "location": "Santa Cruz, CA", "vertical": "green_transportation", "year": 2009},
            {"name": "Rivian", "description": "Electric adventure vehicles and commercial delivery vans", "location": "Irvine, CA", "vertical": "green_transportation", "year": 2009},
            {"name": "Lucid Motors", "description": "Ultra-long-range luxury electric sedans with cutting-edge battery tech", "location": "Newark, CA", "vertical": "green_transportation", "year": 2007},
            {"name": "Volta Industries", "description": "EV charging network at high-traffic retail locations", "location": "San Francisco, CA", "vertical": "green_transportation", "year": 2010},
            {"name": "Einride", "description": "Autonomous electric and hydrogen freight transport platform", "location": "Stockholm, Sweden", "vertical": "green_transportation", "year": 2016},
            {"name": "Lilium", "description": "Electric vertical takeoff and landing jets for regional air mobility", "location": "Munich, Germany", "vertical": "green_transportation", "year": 2015},
            {"name": "Arcimoto", "description": "Ultra-efficient electric vehicles for everyday trips and last-mile delivery", "location": "Eugene, OR", "vertical": "green_transportation", "year": 2007},
            {"name": "Arrival", "description": "Electric buses and vans manufactured in microfactories", "location": "London, UK", "vertical": "green_transportation", "year": 2015},
            {"name": "Lightning eMotors", "description": "Zero-emission medium-duty commercial vehicles and charging systems", "location": "Loveland, CO", "vertical": "green_transportation", "year": 2009},
            {"name": "Proterra", "description": "Electric buses and charging infrastructure for transit agencies", "location": "Burlingame, CA", "vertical": "green_transportation", "year": 2004},
            {"name": "Xos Trucks", "description": "Electric medium and heavy-duty commercial trucks for fleets", "location": "North Hollywood, CA", "vertical": "green_transportation", "year": 2016},
            {"name": "Nikola Motor", "description": "Hydrogen fuel cell and battery-electric semi-trucks", "location": "Phoenix, AZ", "vertical": "green_transportation", "year": 2014},
            {"name": "Hyzon Motors", "description": "Hydrogen fuel cell commercial trucks and buses for zero-emission fleets", "location": "Rochester, NY", "vertical": "green_transportation", "year": 2019},
            {"name": "Sono Motors", "description": "Solar-powered electric vehicles with integrated solar cells", "location": "Munich, Germany", "vertical": "green_transportation", "year": 2016},
            {"name": "Aptera", "description": "Solar electric vehicle with 1000-mile range using integrated panels", "location": "San Diego, CA", "vertical": "green_transportation", "year": 2005},
            {"name": "ZeroAvia", "description": "Hydrogen-electric powertrains for zero-emission commercial aviation", "location": "Hollister, CA", "vertical": "green_transportation", "year": 2017},
            {"name": "Universal Hydrogen", "description": "Hydrogen fuel cartridge distribution network for regional aircraft", "location": "Hawthorne, CA", "vertical": "green_transportation", "year": 2020},
            {"name": "Heart Aerospace", "description": "Regional electric aircraft with 200-passenger capacity", "location": "Gothenburg, Sweden", "vertical": "green_transportation", "year": 2018},
            {"name": "Stable Auto", "description": "Fleet electrification software for managing EV charging at scale", "location": "San Francisco, CA", "vertical": "green_transportation", "year": 2018},
            {"name": "Electrify America", "description": "Fast EV charging network across the US with 3500+ chargers", "location": "Reston, VA", "vertical": "green_transportation", "year": 2016},
            {"name": "ChargePoint", "description": "EV charging network with 250,000+ charging ports worldwide", "location": "Campbell, CA", "vertical": "green_transportation", "year": 2007},
            {"name": "Blink Charging", "description": "EV charging infrastructure for residential and commercial locations", "location": "Miami Beach, FL", "vertical": "green_transportation", "year": 2009},
            {"name": "Freewire Technologies", "description": "Ultrafast EV charging with integrated battery for grid-constrained sites", "location": "Oakland, CA", "vertical": "green_transportation", "year": 2014},
            {"name": "Tritium", "description": "DC fast chargers for public and commercial EV charging networks", "location": "Brisbane, Australia", "vertical": "green_transportation", "year": 2001},

            # ── Sustainable Agriculture ────────────────────────────────────────────
            {"name": "Pivot Bio", "description": "Microbial nitrogen for corn and wheat, replacing synthetic fertilizer", "location": "Berkeley, CA", "vertical": "sustainable_agriculture", "year": 2011},
            {"name": "Apeel Sciences", "description": "Plant-derived coatings that extend produce shelf life by 2-3x", "location": "Goleta, CA", "vertical": "sustainable_agriculture", "year": 2012},
            {"name": "Bowery Farming", "description": "Indoor vertical farming using zero pesticides and 95% less water", "location": "New York, NY", "vertical": "sustainable_agriculture", "year": 2015},
            {"name": "Sound Agriculture", "description": "Nutrient efficiency biologicals improving crop yields with less input", "location": "Emeryville, CA", "vertical": "sustainable_agriculture", "year": 2015},
            {"name": "Plenty", "description": "Indoor vertical farming using AI-optimized lighting and robotics", "location": "San Francisco, CA", "vertical": "sustainable_agriculture", "year": 2013},
            {"name": "AppHarvest", "description": "Large-scale high-tech indoor farms in Appalachia for tomatoes", "location": "Morehead, KY", "vertical": "sustainable_agriculture", "year": 2017},
            {"name": "AeroFarms", "description": "Aeroponic indoor vertical farms producing leafy greens with minimal water", "location": "Newark, NJ", "vertical": "sustainable_agriculture", "year": 2004},
            {"name": "Infarm", "description": "Modular indoor farming units deployed in supermarkets and distribution centers", "location": "Berlin, Germany", "vertical": "sustainable_agriculture", "year": 2013},
            {"name": "Mosa Meat", "description": "Cultivated beef grown from animal cells without slaughter", "location": "Maastricht, Netherlands", "vertical": "sustainable_agriculture", "year": 2016},
            {"name": "UPSIDE Foods", "description": "Cultivated chicken and beef grown from cells in bioreactors", "location": "Berkeley, CA", "vertical": "sustainable_agriculture", "year": 2015},
            {"name": "Impossible Foods", "description": "Plant-based meat products that look and taste like animal meat", "location": "Redwood City, CA", "vertical": "sustainable_agriculture", "year": 2011},
            {"name": "Beyond Meat", "description": "Plant-based burgers, sausages, and chicken from pea protein", "location": "El Segundo, CA", "vertical": "sustainable_agriculture", "year": 2009},
            {"name": "Perfect Day", "description": "Animal-free dairy proteins made through precision fermentation", "location": "Berkeley, CA", "vertical": "sustainable_agriculture", "year": 2014},
            {"name": "Oatly", "description": "Oat-based milk and dairy alternatives with lower carbon footprint", "location": "Malmo, Sweden", "vertical": "sustainable_agriculture", "year": 1994},
            {"name": "Indigo Agriculture", "description": "Microbial crop treatments and grain marketplace for sustainable farming", "location": "Boston, MA", "vertical": "sustainable_agriculture", "year": 2014},
            {"name": "Benson Hill", "description": "CropOS platform unlocking crop genetic diversity for plant-based ingredients", "location": "St. Louis, MO", "vertical": "sustainable_agriculture", "year": 2012},
            {"name": "AgBiome", "description": "Biologicals for crop protection replacing synthetic pesticides", "location": "Research Triangle, NC", "vertical": "sustainable_agriculture", "year": 2012},
            {"name": "Farmers Business Network", "description": "Farmer-to-farmer network and marketplace for crop inputs and insights", "location": "San Carlos, CA", "vertical": "sustainable_agriculture", "year": 2014},
            {"name": "Granular", "description": "Farm management software for planning, tracking, and analysis", "location": "San Francisco, CA", "vertical": "sustainable_agriculture", "year": 2014},
            {"name": "Prospera", "description": "AI-powered crop monitoring and disease detection for greenhouses", "location": "Tel Aviv, Israel", "vertical": "sustainable_agriculture", "year": 2014},

            # ── Built Environment ──────────────────────────────────────────────────
            {"name": "BlocPower", "description": "Green building electrification financing for underserved urban buildings", "location": "New York, NY", "vertical": "built_environment", "year": 2014},
            {"name": "Turntide Technologies", "description": "Smart motor systems that cut HVAC energy consumption by 50%", "location": "San Jose, CA", "vertical": "built_environment", "year": 2013},
            {"name": "Dandelion Energy", "description": "Home geothermal heating and cooling using ground-source heat pumps", "location": "Mount Kisco, NY", "vertical": "built_environment", "year": 2017},
            {"name": "Sealed", "description": "Whole-home energy efficiency upgrades with zero upfront cost financing", "location": "New York, NY", "vertical": "built_environment", "year": 2012},
            {"name": "Budderfly", "description": "Energy efficiency as a service for commercial buildings with no capital", "location": "Shelton, CT", "vertical": "built_environment", "year": 2016},
            {"name": "Nuvve", "description": "Vehicle-to-grid technology turning EV batteries into distributed storage", "location": "San Diego, CA", "vertical": "built_environment", "year": 2010},
            {"name": "Measurabl", "description": "ESG data management for commercial real estate portfolios", "location": "San Diego, CA", "vertical": "built_environment", "year": 2013},
            {"name": "CarbonCure Technologies", "description": "Injecting CO2 into concrete during mixing for stronger, greener concrete", "location": "Halifax, Canada", "vertical": "built_environment", "year": 2007},
            {"name": "Brimstone Energy", "description": "Carbon-negative cement made from calcium silicate without fossil fuels", "location": "Oakland, CA", "vertical": "built_environment", "year": 2019},
            {"name": "Holcim Lafarge", "description": "Global building materials company with low-carbon ECOPact concrete line", "location": "Zurich, Switzerland", "vertical": "built_environment", "year": 1833},
            {"name": "Solugen", "description": "Carbon-negative specialty chemicals using bioengineered enzymes at scale", "location": "Houston, TX", "vertical": "built_environment", "year": 2016},
            {"name": "Pearl Certification", "description": "Green home certification quantifying energy features for home value", "location": "Charlottesville, VA", "vertical": "built_environment", "year": 2010},
            {"name": "Verdagy", "description": "Next-generation water electrolysis for low-cost green hydrogen", "location": "Monterey, CA", "vertical": "built_environment", "year": 2020},
            {"name": "Maderight", "description": "Supply chain traceability and sustainability for apparel factories", "location": "New York, NY", "vertical": "built_environment", "year": 2019},
            {"name": "Pearl X", "description": "Commercial solar + battery + EV charging platform for building owners", "location": "San Francisco, CA", "vertical": "built_environment", "year": 2020},
            {"name": "View", "description": "Smart dynamic glass that automatically tints to optimize energy and comfort", "location": "Milpitas, CA", "vertical": "built_environment", "year": 2007},
            {"name": "Envoy Technologies", "description": "Shared electric vehicles for apartment communities and offices", "location": "Culver City, CA", "vertical": "built_environment", "year": 2018},

            # ── Circular Economy ───────────────────────────────────────────────────
            {"name": "Ginkgo Bioworks", "description": "Cell programming platform for biological products replacing petrochemicals", "location": "Boston, MA", "vertical": "circular_economy", "year": 2009},
            {"name": "Nth Cycle", "description": "Critical mineral recycling from e-waste using electroextraction", "location": "Boston, MA", "vertical": "circular_economy", "year": 2019},
            {"name": "Novamont", "description": "Bioplastics and bioproducts from renewable agricultural resources", "location": "Novara, Italy", "vertical": "circular_economy", "year": 1990},
            {"name": "Renewlogy", "description": "Plastic waste conversion to fuel using pyrolysis technology", "location": "Salt Lake City, UT", "vertical": "circular_economy", "year": 2011},
            {"name": "Plastic Energy", "description": "Chemical recycling of end-of-life plastics to oil feedstock", "location": "London, UK", "vertical": "circular_economy", "year": 2013},
            {"name": "Epoch Biodesign", "description": "Enzymes that break down mixed plastics into their component monomers", "location": "London, UK", "vertical": "circular_economy", "year": 2019},
            {"name": "Carbios", "description": "Enzymatic PET plastic recycling at industrial scale", "location": "Catoire-Vaupe, France", "vertical": "circular_economy", "year": 2011},
            {"name": "Origin Materials", "description": "Carbon-negative PET plastic from wood waste and agricultural residue", "location": "West Sacramento, CA", "vertical": "circular_economy", "year": 2008},
            {"name": "Infinitum Electric", "description": "Printed circuit board motors that are lighter and more recyclable", "location": "Austin, TX", "vertical": "circular_economy", "year": 2016},
            {"name": "Bolt Threads", "description": "Sustainable mycelium leather and spider-silk protein materials", "location": "Emeryville, CA", "vertical": "circular_economy", "year": 2009},
            {"name": "Modern Meadow", "description": "Biofabricated leather and materials grown from yeast fermentation", "location": "Nutley, NJ", "vertical": "circular_economy", "year": 2012},
            {"name": "Natural Fiber Welding", "description": "Plant-based leather alternatives using welded natural fibers", "location": "Peoria, IL", "vertical": "circular_economy", "year": 2015},
            {"name": "TerraCycle", "description": "Recycling hard-to-recycle materials and circular packaging programs", "location": "Trenton, NJ", "vertical": "circular_economy", "year": 2001},
            {"name": "Resynergi", "description": "Microwave-based plastic pyrolysis system for chemical recycling", "location": "Santa Rosa, CA", "vertical": "circular_economy", "year": 2020},
            {"name": "gr3n", "description": "Microwave-assisted alkaline hydrolysis to depolymerize PET plastics", "location": "Zurich, Switzerland", "vertical": "circular_economy", "year": 2018},
            {"name": "Loop Industries", "description": "Chemical depolymerization of PET and polyester for virgin-quality recycling", "location": "Montreal, Canada", "vertical": "circular_economy", "year": 2015},

            # ── Climate Fintech ────────────────────────────────────────────────────
            {"name": "Watershed", "description": "Enterprise carbon management, accounting, and reporting platform", "location": "San Francisco, CA", "vertical": "climate_fintech", "year": 2019},
            {"name": "Persefoni", "description": "Climate management and accounting platform for enterprises and finance", "location": "Scottsdale, AZ", "vertical": "climate_fintech", "year": 2020},
            {"name": "Xpansiv", "description": "Market infrastructure for environmental commodities and carbon credits", "location": "San Francisco, CA", "vertical": "climate_fintech", "year": 2019},
            {"name": "Rubicon Carbon", "description": "Carbon credit portfolio management and trading platform for enterprises", "location": "New York, NY", "vertical": "climate_fintech", "year": 2022},
            {"name": "Patch", "description": "Carbon removal API for businesses to integrate carbon offsetting", "location": "San Francisco, CA", "vertical": "climate_fintech", "year": 2020},
            {"name": "Cloverly", "description": "Carbon API enabling ecommerce and fintech to offset transactions", "location": "Birmingham, AL", "vertical": "climate_fintech", "year": 2019},
            {"name": "Chooose", "description": "Climate subscription platform for individuals and businesses to act on carbon", "location": "Oslo, Norway", "vertical": "climate_fintech", "year": 2018},
            {"name": "Aspiration", "description": "Sustainable banking and investing app with carbon offsetting features", "location": "Los Angeles, CA", "vertical": "climate_fintech", "year": 2013},
            {"name": "Atmos Financial", "description": "Climate-focused online bank investing deposits in green projects", "location": "San Francisco, CA", "vertical": "climate_fintech", "year": 2020},
            {"name": "Clim8 Invest", "description": "Investment app focused exclusively on climate-positive companies", "location": "London, UK", "vertical": "climate_fintech", "year": 2019},
            {"name": "Doconomy", "description": "Credit card tracking carbon footprint of purchases to cap emissions", "location": "Stockholm, Sweden", "vertical": "climate_fintech", "year": 2018},
            {"name": "Greenly", "description": "Carbon footprint measurement platform for SMEs with real-time tracking", "location": "Paris, France", "vertical": "climate_fintech", "year": 2019},
            {"name": "Normative", "description": "Carbon accounting software for scope 1, 2, and 3 emissions reporting", "location": "Stockholm, Sweden", "vertical": "climate_fintech", "year": 2014},
            {"name": "Sweep", "description": "Enterprise carbon management for tracking, reporting, and reducing emissions", "location": "London, UK", "vertical": "climate_fintech", "year": 2020},
            {"name": "Net Purpose", "description": "ESG data platform connecting capital to measurable impact", "location": "London, UK", "vertical": "climate_fintech", "year": 2019},
            {"name": "Sphera", "description": "ESG performance management software for large enterprises", "location": "Chicago, IL", "vertical": "climate_fintech", "year": 1992},
            {"name": "Clarity AI", "description": "Sustainability analytics for investors integrating ESG data at scale", "location": "New York, NY", "vertical": "climate_fintech", "year": 2017},
            {"name": "Measurabl", "description": "Real estate ESG data management and sustainability reporting", "location": "San Diego, CA", "vertical": "climate_fintech", "year": 2013},

            # ── Water & Ocean ──────────────────────────────────────────────────────
            {"name": "Energy Recovery", "description": "Pressure exchanger energy recovery devices for seawater desalination", "location": "San Leandro, CA", "vertical": "water_ocean", "year": 1992},
            {"name": "Gradiant", "description": "Novel water treatment technology for industrial and municipal wastewater", "location": "Boston, MA", "vertical": "water_ocean", "year": 2013},
            {"name": "Aquacycl", "description": "Continuous flow bioelectrochemical wastewater treatment systems", "location": "San Diego, CA", "vertical": "water_ocean", "year": 2018},
            {"name": "WaterBit", "description": "Wireless IoT irrigation management for precision water savings in farms", "location": "San Jose, CA", "vertical": "water_ocean", "year": 2014},
            {"name": "Valor Water Analytics", "description": "AI-powered water loss detection and demand analytics for utilities", "location": "San Francisco, CA", "vertical": "water_ocean", "year": 2013},
            {"name": "Xylem", "description": "Water technology solutions for transport, testing, and treatment at scale", "location": "Rye Brook, NY", "vertical": "water_ocean", "year": 2011},
            {"name": "Seachange", "description": "CO2-to-kelp ocean carbon removal using kelp farm installations", "location": "San Diego, CA", "vertical": "water_ocean", "year": 2022},
            {"name": "Brilliant Planet", "description": "Scalable algae-based carbon removal and sequestration in coastal deserts", "location": "London, UK", "vertical": "water_ocean", "year": 2013},
            {"name": "Kelp Blue", "description": "Giant kelp forest restoration for carbon sequestration and biodiversity", "location": "Windhoek, Namibia", "vertical": "water_ocean", "year": 2019},
            {"name": "Planetary Technologies", "description": "Ocean alkalinity enhancement to draw down atmospheric CO2 at scale", "location": "Halifax, Canada", "vertical": "water_ocean", "year": 2019},
            {"name": "Ebb Carbon", "description": "Ocean alkalinity enhancement for gigaton-scale marine carbon removal", "location": "South San Francisco, CA", "vertical": "water_ocean", "year": 2021},
            {"name": "The Ocean Cleanup", "description": "Large-scale systems to remove plastic from oceans and river sources", "location": "Rotterdam, Netherlands", "vertical": "water_ocean", "year": 2013},
            {"name": "4ocean", "description": "Ocean plastic cleanup and removal funded through product sales", "location": "Boca Raton, FL", "vertical": "water_ocean", "year": 2017},
            {"name": "Blue Frontier", "description": "Seawater-powered air conditioning for coastal buildings", "location": "Fort Lauderdale, FL", "vertical": "water_ocean", "year": 2020},
            {"name": "Salinity Solutions", "description": "Low-energy reverse osmosis for rural and off-grid water purification", "location": "Bristol, UK", "vertical": "water_ocean", "year": 2020},

            # ── Industrial Decarbonization ─────────────────────────────────────────
            {"name": "Boston Metal", "description": "Molten oxide electrolysis for zero-carbon steel production", "location": "Woburn, MA", "vertical": "industrial_decarbonization", "year": 2012},
            {"name": "Electra Steel", "description": "Low-temperature electrochemical iron production using renewable electricity", "location": "Boulder, CO", "vertical": "industrial_decarbonization", "year": 2020},
            {"name": "Sublime Systems", "description": "Electrochemical cement production replacing high-carbon kilns", "location": "Somerville, MA", "vertical": "industrial_decarbonization", "year": 2020},
            {"name": "Twelve", "description": "Electrochemical CO2 conversion to chemicals, fuels, and materials", "location": "Berkeley, CA", "vertical": "industrial_decarbonization", "year": 2015},
            {"name": "Fortescue Future Industries", "description": "Green hydrogen production and industrial decarbonization at scale", "location": "Perth, Australia", "vertical": "industrial_decarbonization", "year": 2020},
            {"name": "Plug Power", "description": "Green hydrogen fuel cell systems for industrial forklifts and mobility", "location": "Latham, NY", "vertical": "industrial_decarbonization", "year": 1997},
            {"name": "Nel Hydrogen", "description": "Hydrogen electrolyzers and fueling stations for industrial green hydrogen", "location": "Oslo, Norway", "vertical": "industrial_decarbonization", "year": 1927},
            {"name": "ITM Power", "description": "PEM electrolyzer systems for green hydrogen production at scale", "location": "Sheffield, UK", "vertical": "industrial_decarbonization", "year": 2001},
            {"name": "Sunfire", "description": "High-temperature electrolysis and co-electrolysis for industrial decarbonization", "location": "Dresden, Germany", "vertical": "industrial_decarbonization", "year": 2010},
            {"name": "Electric Hydrogen", "description": "Gigawatt-scale PEM electrolyzers for low-cost green hydrogen", "location": "San Carlos, CA", "vertical": "industrial_decarbonization", "year": 2020},
            {"name": "Hystar", "description": "High-efficiency PEM electrolyzers for green hydrogen production", "location": "Oslo, Norway", "vertical": "industrial_decarbonization", "year": 2019},
            {"name": "H2Pro", "description": "E-TAC water splitting technology for low-cost green hydrogen", "location": "Caesarea, Israel", "vertical": "industrial_decarbonization", "year": 2019},
            {"name": "Hysata", "description": "Capillary-fed electrolysis cells for 95% efficient green hydrogen", "location": "Wollongong, Australia", "vertical": "industrial_decarbonization", "year": 2021},
            {"name": "Lydian", "description": "Industrial heat decarbonization using electric arc technology", "location": "Boston, MA", "vertical": "industrial_decarbonization", "year": 2022},
            {"name": "Revel Energy", "description": "Green ammonia production using offshore wind and electrolysis", "location": "San Diego, CA", "vertical": "industrial_decarbonization", "year": 2021},
            {"name": "Monolith Materials", "description": "Methane pyrolysis producing clean hydrogen and carbon black", "location": "Lincoln, NE", "vertical": "industrial_decarbonization", "year": 2012},
            {"name": "C-Zero", "description": "Methane pyrolysis for blue hydrogen with solid carbon coproduct", "location": "Santa Barbara, CA", "vertical": "industrial_decarbonization", "year": 2018},

            # ── Climate Adaptation ─────────────────────────────────────────────────
            {"name": "Jupiter Intelligence", "description": "Climate risk analytics for infrastructure, real estate, and finance", "location": "San Mateo, CA", "vertical": "climate_adaptation", "year": 2017},
            {"name": "Kettle", "description": "Reinsurance for wildfire using ML risk modeling and real-time data", "location": "San Francisco, CA", "vertical": "climate_adaptation", "year": 2020},
            {"name": "One Concern", "description": "AI-powered disaster resilience platform for cities and businesses", "location": "Palo Alto, CA", "vertical": "climate_adaptation", "year": 2015},
            {"name": "Cervest", "description": "Climate intelligence platform quantifying physical climate risk for assets", "location": "London, UK", "vertical": "climate_adaptation", "year": 2016},
            {"name": "ClimateAI", "description": "AI-powered climate risk analytics for supply chains and operations", "location": "San Francisco, CA", "vertical": "climate_adaptation", "year": 2018},
            {"name": "Sust Global", "description": "Satellite-based climate and physical risk data for financial institutions", "location": "San Francisco, CA", "vertical": "climate_adaptation", "year": 2021},
            {"name": "Salient Predictions", "description": "Subseasonal weather forecasting for energy, agriculture, and insurance", "location": "Boston, MA", "vertical": "climate_adaptation", "year": 2019},
            {"name": "Tomorrow.io", "description": "Weather intelligence platform for real-time climate data and forecasting", "location": "Boston, MA", "vertical": "climate_adaptation", "year": 2016},
            {"name": "Descartes Labs", "description": "Satellite imagery analytics for agriculture, energy, and climate monitoring", "location": "Santa Fe, NM", "vertical": "climate_adaptation", "year": 2014},
            {"name": "Resilience", "description": "Cyber and climate risk insurance and resilience platform", "location": "San Francisco, CA", "vertical": "climate_adaptation", "year": 2016},
            {"name": "Aon Impact Forecasting", "description": "Catastrophe modeling and climate risk analytics for the insurance industry", "location": "Chicago, IL", "vertical": "climate_adaptation", "year": 1997},
            {"name": "FloodMapp", "description": "Real-time flood intelligence and warning systems for emergency managers", "location": "Brisbane, Australia", "vertical": "climate_adaptation", "year": 2019},
            {"name": "Zesty.ai", "description": "AI-powered wildfire and flood risk scoring for property insurance", "location": "San Francisco, CA", "vertical": "climate_adaptation", "year": 2017},
            {"name": "Riskthinking.AI", "description": "Climate scenario analytics for financial portfolios and investment risk", "location": "Toronto, Canada", "vertical": "climate_adaptation", "year": 2020},

            # ── Grid & Energy Management ───────────────────────────────────────────
            {"name": "AutoGrid", "description": "AI-powered energy flexibility and demand response management platform", "location": "Redwood City, CA", "vertical": "grid_energy_management", "year": 2011},
            {"name": "Leap", "description": "Virtual power plant network aggregating distributed energy resources", "location": "San Francisco, CA", "vertical": "grid_energy_management", "year": 2018},
            {"name": "Enbala Power Networks", "description": "Real-time distributed energy resource optimization for grid operators", "location": "Vancouver, BC", "vertical": "grid_energy_management", "year": 2003},
            {"name": "Voltus", "description": "Demand response and distributed energy resource management platform", "location": "San Francisco, CA", "vertical": "grid_energy_management", "year": 2016},
            {"name": "Virtual Peaker", "description": "Demand side management platform for utilities managing distributed resources", "location": "Louisville, KY", "vertical": "grid_energy_management", "year": 2016},
            {"name": "Upside Energy", "description": "Virtual energy storage platform using distributed EV and building assets", "location": "Manchester, UK", "vertical": "grid_energy_management", "year": 2013},
            {"name": "Sympower", "description": "Demand flexibility aggregation for industrial and commercial customers", "location": "Amsterdam, Netherlands", "vertical": "grid_energy_management", "year": 2016},
            {"name": "GridBeyond", "description": "AI-powered energy intelligence platform for industrial demand response", "location": "Dublin, Ireland", "vertical": "grid_energy_management", "year": 2014},
            {"name": "CPower Energy", "description": "Demand response and energy optimization for commercial facilities", "location": "Baltimore, MD", "vertical": "grid_energy_management", "year": 2008},
            {"name": "Piclo", "description": "Digital marketplace for flexible grid services and energy balancing", "location": "London, UK", "vertical": "grid_energy_management", "year": 2015},
            {"name": "EnerNOC", "description": "Energy intelligence software and demand response for utilities and businesses", "location": "Boston, MA", "vertical": "grid_energy_management", "year": 2003},
            {"name": "Extensible Energy", "description": "Cloud-based energy management and demand flexibility for buildings", "location": "Berkeley, CA", "vertical": "grid_energy_management", "year": 2013},
            {"name": "Sense", "description": "Home energy monitor identifying appliance-level consumption patterns", "location": "Cambridge, MA", "vertical": "grid_energy_management", "year": 2013},
            {"name": "Bidgee", "description": "Smart water and energy analytics for utilities using AMI data", "location": "San Luis Obispo, CA", "vertical": "grid_energy_management", "year": 2009},
        ]

        startups = []
        for company in companies:
            primary_vertical, secondary = self.category_mapper.map_startup(
                company["name"], company["description"]
            )
            startup = {
                "name": company["name"],
                "short_description": company["description"],
                "headquarters_location": company.get("location", ""),
                "founded_year": company.get("year"),
                "primary_vertical": primary_vertical or company.get("vertical", "clean_energy"),
                "secondary_verticals": secondary,
                "source": "curated",
                "source_id": re.sub(r"[^a-z0-9]", "-", company["name"].lower())[:50],
                "website_url": "",
            }
            startups.append(startup)

        logger.info(f"Loaded {len(startups)} curated climate companies")
        return startups

    def generate_sample_data(self, count: int = 300) -> List[Dict[str, Any]]:
        """Generate sample climate startup data for development/testing."""
        import random

        logger.info(f"Generating {count} sample climate startups...")

        verticals = list(self.category_mapper.verticals.keys())

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
                "Second-life EV battery repurposing platform",
            ],
            "green_transportation": [
                "Electric aircraft for regional zero-emission travel",
                "EV charging network with smart load balancing",
                "Sustainable aviation fuel from agricultural waste",
                "Electric ferry systems for urban waterways",
            ],
            "sustainable_agriculture": [
                "Vertical farming with 95% water savings",
                "Precision agriculture using satellite imagery",
                "Alternative protein from precision fermentation",
                "Regenerative agriculture soil carbon monitoring",
            ],
            "built_environment": [
                "Smart HVAC systems reducing energy consumption 40%",
                "Low-carbon concrete using industrial waste",
                "Building energy management and optimization platform",
                "Heat pump systems for commercial building retrofits",
            ],
            "circular_economy": [
                "Chemical recycling of mixed plastics to virgin quality",
                "Textile-to-textile fiber recycling technology",
                "Electronics refurbishment and resale marketplace",
                "Food waste conversion to biofuel and nutrients",
            ],
            "climate_fintech": [
                "Carbon footprint tracking platform for businesses",
                "ESG data analytics and reporting for investors",
                "Climate risk assessment tools for insurers",
                "Green bond verification and issuance platform",
            ],
            "water_ocean": [
                "Solar-powered desalination for remote communities",
                "AI-powered wastewater treatment optimization",
                "Seaweed farming for carbon credits and food",
                "Ocean plastic collection and recycling technology",
            ],
            "industrial_decarbonization": [
                "Green hydrogen electrolyzer for industrial processes",
                "Electric arc furnace for low-carbon steel production",
                "Industrial heat pump systems for process heat",
                "Green ammonia production using renewable electricity",
            ],
            "climate_adaptation": [
                "Wildfire detection and early warning using satellites",
                "Flood prediction and risk modeling for cities",
                "Climate-resilient drought-tolerant crop varieties",
                "Coastal protection infrastructure using natural solutions",
            ],
            "grid_energy_management": [
                "Virtual power plant software aggregating distributed assets",
                "AI demand response optimization for utilities",
                "Microgrid controller for resilient community energy",
                "Grid-scale power electronics for renewable integration",
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
            base = random.choice(["Solar", "Carbon", "Grid", "Battery", "Wind", "Hydro",
                                   "Eco", "Circular", "Ocean", "Steel", "Flood", "Power"])
            suffix = random.choice(["AI", "Tech", "Systems", "Solutions", "Labs", "Energy", ""])
            name = f"{base}{suffix}".strip()
            if i // 20 > 0:
                name = f"{name} {i // 20}"
            while name in used_names:
                name = f"{name}{random.randint(1, 99)}"
            used_names.add(name)

            descs = sample_descriptions.get(vertical, ["Climate technology startup"])
            desc = random.choice(descs)

            funding = None
            if random.random() > 0.3:
                funding = random.choice([
                    random.randint(500_000, 5_000_000),
                    random.randint(5_000_000, 30_000_000),
                    random.randint(30_000_000, 150_000_000),
                ])

            year = random.choices(
                range(2010, 2025),
                weights=[1, 1, 2, 2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 8, 5],
                k=1,
            )[0]

            startup = {
                "name": name,
                "short_description": desc,
                "long_description": f"{desc} We are focused on {self.category_mapper.get_vertical_name(vertical).lower()} solutions.",
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
                "technologies": self.category_mapper.extract_keywords(desc),
                "keywords": self.category_mapper.verticals[vertical].get("keywords", [])[:5],
                "source": "sample",
                "source_id": f"sample_{i}",
            }
            startups.append(startup)

        logger.info(f"Generated {len(startups)} sample startups")
        return startups

    async def scrape_all_sources(self) -> int:
        """Scrape from all sources. Uses Firecrawl if API key is set, else curated list."""
        all_startups = []

        firecrawl_key = getattr(settings, "firecrawl_api_key", "") or ""

        if firecrawl_key:
            logger.info("Firecrawl API key found — using Firecrawl for comprehensive scraping")
            try:
                fc = FirecrawlScraper(self.db, firecrawl_key)
                saved = fc.scrape_all_sources()
                logger.info(f"Firecrawl scraping complete: {saved} startups saved")
                # Also load the curated list to ensure we have good baseline data
                logger.info("Adding curated list to supplement Firecrawl data...")
                curated = await self.scrape_yc_climate()
                for s in curated:
                    self.db.insert_startup(s)
                return self.db.get_startup_count()
            except Exception as e:
                logger.error(f"Firecrawl scraping failed, falling back to curated list: {e}")

        # Fallback / default: large curated list
        logger.info("Using curated climate startup list...")
        curated = await self.scrape_yc_climate()
        all_startups.extend(curated)

        saved = sum(1 for s in all_startups if self.db.insert_startup(s))
        logger.info(f"Saved {saved} startups to database")
        return saved
