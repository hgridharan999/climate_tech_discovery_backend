# -*- coding: utf-8 -*-
"""Generate sample climate startup data for development and testing."""

import sys
import os
import random
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.database import Database
from src.core.config import settings

# Sample climate startups data
SAMPLE_STARTUPS = [
    # Carbon Management
    {"name": "CarbonCure", "short_description": "Injecting captured CO2 into concrete to reduce carbon footprint and improve concrete strength", "founded_year": 2012, "total_funding_usd": 85000000, "website_url": "https://carboncure.com", "primary_vertical": "carbon_management", "headquarters_location": "Halifax, Canada"},
    {"name": "Climeworks", "short_description": "Direct air capture technology to remove CO2 from atmosphere and store it permanently underground", "founded_year": 2009, "total_funding_usd": 650000000, "website_url": "https://climeworks.com", "primary_vertical": "carbon_management", "headquarters_location": "Zurich, Switzerland"},
    {"name": "Running Tide", "short_description": "Ocean-based carbon removal using kelp forests and carbon-rich biomass sinking", "founded_year": 2017, "total_funding_usd": 48000000, "website_url": "https://runningtide.com", "primary_vertical": "carbon_management", "headquarters_location": "Portland, USA"},
    
    # Clean Energy
    {"name": "Heliogen", "short_description": "Concentrating solar thermal energy to replace fossil fuels in industrial processes", "founded_year": 2013, "total_funding_usd": 148000000, "website_url": "https://heliogen.com", "primary_vertical": "clean_energy", "headquarters_location": "Pasadena, USA"},
    {"name": "Form Energy", "short_description": "Multi-day iron-air batteries for renewable energy storage at grid scale", "founded_year": 2017, "total_funding_usd": 829000000, "website_url": "https://formenergy.com", "primary_vertical": "energy_storage", "headquarters_location": "Boston, USA"},
    {"name": "Orsted", "short_description": "Global leader in offshore wind farms and renewable energy development", "founded_year": 1972, "total_funding_usd": 12000000000, "website_url": "https://orsted.com", "primary_vertical": "clean_energy", "headquarters_location": "Copenhagen, Denmark"},
    {"name": "Sunrun", "short_description": "Residential solar panels and battery storage systems across the United States", "founded_year": 2007, "total_funding_usd": 3600000000, "website_url": "https://sunrun.com", "primary_vertical": "clean_energy", "headquarters_location": "San Francisco, USA"},
    
    # Energy Storage
    {"name": "QuantumScape", "short_description": "Solid-state lithium-metal batteries for electric vehicles with faster charging", "founded_year": 2010, "total_funding_usd": 1400000000, "website_url": "https://quantumscape.com", "primary_vertical": "energy_storage", "headquarters_location": "San Jose, USA"},
    {"name": "Northvolt", "short_description": "European lithium-ion battery gigafactory with recycling capabilities", "founded_year": 2016, "total_funding_usd": 9000000000, "website_url": "https://northvolt.com", "primary_vertical": "energy_storage", "headquarters_location": "Stockholm, Sweden"},
    {"name": "Energy Vault", "short_description": "Gravity-based energy storage using cranes and massive blocks", "founded_year": 2017, "total_funding_usd": 536000000, "website_url": "https://energyvault.com", "primary_vertical": "energy_storage", "headquarters_location": "Westlake Village, USA"},
    
    # Green Transportation
    {"name": "Rivian", "short_description": "Electric adventure vehicles including pickup trucks and delivery vans", "founded_year": 2009, "total_funding_usd": 13700000000, "website_url": "https://rivian.com", "primary_vertical": "green_transportation", "headquarters_location": "Irvine, USA"},
    {"name": "Lilium", "short_description": "Electric vertical takeoff and landing aircraft for regional air mobility", "founded_year": 2015, "total_funding_usd": 1500000000, "website_url": "https://lilium.com", "primary_vertical": "green_transportation", "headquarters_location": "Munich, Germany"},
    {"name": "Arrival", "short_description": "Electric delivery vans and buses with microfactories for local production", "founded_year": 2015, "total_funding_usd": 660000000, "website_url": "https://arrival.com", "primary_vertical": "green_transportation", "headquarters_location": "London, UK"},
    {"name": "ChargePoint", "short_description": "EV charging network with thousands of stations across North America and Europe", "founded_year": 2007, "total_funding_usd": 958000000, "website_url": "https://chargepoint.com", "primary_vertical": "green_transportation", "headquarters_location": "Campbell, USA"},
    
    # Sustainable Agriculture
    {"name": "Apeel Sciences", "short_description": "Plant-based coating to extend shelf life of fresh produce and reduce food waste", "founded_year": 2012, "total_funding_usd": 635000000, "website_url": "https://apeelsciences.com", "primary_vertical": "sustainable_agriculture", "headquarters_location": "Santa Barbara, USA"},
    {"name": "Plenty", "short_description": "Indoor vertical farms using 95% less water with no pesticides", "founded_year": 2014, "total_funding_usd": 940000000, "website_url": "https://plenty.ag", "primary_vertical": "sustainable_agriculture", "headquarters_location": "San Francisco, USA"},
    {"name": "Impossible Foods", "short_description": "Plant-based meat alternatives using heme protein from soy", "founded_year": 2011, "total_funding_usd": 1900000000, "website_url": "https://impossiblefoods.com", "primary_vertical": "sustainable_agriculture", "headquarters_location": "Redwood City, USA"},
    {"name": "Indigo Agriculture", "short_description": "Microbial seed treatments to improve crop yields and carbon sequestration", "founded_year": 2014, "total_funding_usd": 1400000000, "website_url": "https://indigoag.com", "primary_vertical": "sustainable_agriculture", "headquarters_location": "Boston, USA"},
    
    # Built Environment
    {"name": "BlocPower", "short_description": "Electrifying and greening buildings with heat pumps and solar installations", "founded_year": 2014, "total_funding_usd": 250000000, "website_url": "https://blocpower.io", "primary_vertical": "built_environment", "headquarters_location": "New York, USA"},
    {"name": "Dandelion Energy", "short_description": "Affordable geothermal heating and cooling systems for homes", "founded_year": 2017, "total_funding_usd": 86000000, "website_url": "https://dandelionenergy.com", "primary_vertical": "built_environment", "headquarters_location": "Mount Kisco, USA"},
    {"name": "Span", "short_description": "Smart electrical panels with battery integration and load management for homes", "founded_year": 2018, "total_funding_usd": 231000000, "website_url": "https://span.io", "primary_vertical": "built_environment", "headquarters_location": "San Francisco, USA"},
    
    # Additional diverse startups
    {"name": "LanzaTech", "short_description": "Converting industrial waste gases into sustainable fuels and chemicals using microbes", "founded_year": 2005, "total_funding_usd": 500000000, "website_url": "https://lanzatech.com", "primary_vertical": "circular_economy", "headquarters_location": "Chicago, USA"},
    {"name": "Twelve", "short_description": "Carbon transformation technology turning CO2 into chemicals and fuels", "founded_year": 2015, "total_funding_usd": 231000000, "website_url": "https://twelve.co", "primary_vertical": "carbon_management", "headquarters_location": "Berkeley, USA"},
    {"name": "Electric Hydrogen", "short_description": "Low-cost green hydrogen electrolyzers for industrial decarbonization", "founded_year": 2020, "total_funding_usd": 380000000, "website_url": "https://eh2.com", "primary_vertical": "industrial_decarbonization", "headquarters_location": "San Jose, USA"},
    {"name": "ClearFlame", "short_description": "Clean fuel technology for heavy-duty diesel engines using ethanol", "founded_year": 2016, "total_funding_usd": 58000000, "website_url": "https://clearflame.com", "primary_vertical": "green_transportation", "headquarters_location": "Chicago, USA"},
    {"name": "NotCo", "short_description": "AI-powered plant-based food alternatives for milk, meat, and ice cream", "founded_year": 2015, "total_funding_usd": 545000000, "website_url": "https://notco.com", "primary_vertical": "sustainable_agriculture", "headquarters_location": "Santiago, Chile"},
]


def generate_data(num_startups=50):
    """Generate sample data by expanding the base startups with variations."""
    generated = SAMPLE_STARTUPS.copy()
    
    verticals = [
        "carbon_management", "clean_energy", "energy_storage", "green_transportation",
        "sustainable_agriculture", "built_environment", "circular_economy",
        "climate_fintech", "water_ocean", "industrial_decarbonization",
        "climate_adaptation", "grid_energy_management"
    ]
    
    tech_keywords = {
        "carbon_management": ["carbon capture", "DAC", "biochar", "sequestration"],
        "clean_energy": ["solar", "wind", "renewable", "photovoltaic"],
        "energy_storage": ["battery", "storage", "lithium-ion", "grid-scale"],
        "green_transportation": ["electric vehicle", "EV", "charging", "e-mobility"],
        "sustainable_agriculture": ["vertical farming", "agtech", "precision ag", "alternative protein"],
        "built_environment": ["heat pump", "green building", "HVAC", "energy efficiency"],
        "circular_economy": ["recycling", "waste management", "circular", "upcycling"],
        "climate_fintech": ["ESG", "green bonds", "carbon credits", "sustainability"],
        "water_ocean": ["water treatment", "desalination", "ocean", "blue carbon"],
        "industrial_decarbonization": ["green hydrogen", "industrial", "electrolyzer", "heavy industry"],
        "climate_adaptation": ["resilience", "flood protection", "climate risk", "adaptation"],
        "grid_energy_management": ["smart grid", "VPP", "demand response", "grid optimization"]
    }
    
    # Generate additional synthetic startups
    while len(generated) < num_startups:
        vertical = random.choice(verticals)
        keywords = tech_keywords[vertical]
        
        company_num = len(generated) + 1
        name = f"{random.choice(['Green', 'Eco', 'Sustainable', 'Climate', 'Carbon', 'Solar', 'Energy'])}{random.choice(['Tech', 'Solutions', 'Power', 'Systems', 'Energy'])}{company_num}"
        
        description = f"Innovative {random.choice(keywords)} solution for {random.choice(['reducing emissions', 'improving efficiency', 'sustainable operations', 'clean energy'])} in the {vertical.replace('_', ' ')} sector"
        
        startup = {
            "name": name,
            "short_description": description,
            "founded_year": random.randint(2010, 2024),
            "total_funding_usd": random.randint(1000000, 500000000),
            "website_url": f"https://{name.lower().replace(' ', '')}.com",
            "primary_vertical": vertical,
            "headquarters_location": f"{random.choice(['San Francisco', 'New York', 'Boston', 'Seattle', 'Austin', 'London', 'Berlin', 'Stockholm', 'Copenhagen'])}, {random.choice(['USA', 'UK', 'Germany', 'Sweden', 'Denmark'])}"
        }
        
        generated.append(startup)
    
    return generated


def main():
    """Generate sample data and populate database."""
    print("Generating sample climate startup data...")
    
    # Create database directory if it doesn't exist
    db_path = Path(settings.database_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Initialize database
    db = Database(settings.database_path)
    db.create_tables()
    
    # Generate and insert startups
    startups = generate_data(num_startups=100)
    
    print(f"Inserting {len(startups)} startups into database...")
    for startup in startups:
        db.insert_startup(**startup)
    
    print(f"✓ Successfully generated {len(startups)} sample startups")
    print(f"✓ Database created at: {settings.database_path}")
    
    # Print summary
    stats = db.get_stats()
    print("\nDatabase Summary:")
    print(f"Total startups: {stats['total_startups']}")
    print(f"Verticals: {len(stats['verticals'])}")
    print(f"\nTop verticals:")
    for v in sorted(stats['verticals'].items(), key=lambda x: x[1], reverse=True)[:5]:
        print(f"  {v[0]}: {v[1]} startups")


if __name__ == "__main__":
    main()
