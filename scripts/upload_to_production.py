import requests
import sqlite3
import json

# Set your production backend URL
API_URL = "https://climatetechdiscoverybackend-production.up.railway.app/api/startups"

# Path to your local SQLite database
DB_PATH = "data/climate_startups.db"

# Query to fetch all startups
QUERY = "SELECT * FROM startups"

# Map DB row to API payload (adjust keys as needed)
def row_to_payload(row, columns):
    data = dict(zip(columns, row))
    # Remove fields not accepted by API, or adjust as needed
    payload = {
        "name": data.get("name"),
        "short_description": data.get("short_description"),
        "long_description": data.get("long_description"),
        "founded_year": data.get("founded_year"),
        "total_funding_usd": data.get("total_funding_usd"),
        "funding_stage": data.get("funding_stage"),
        "employee_count": data.get("employee_count"),
        "website_url": data.get("website_url"),
        "linkedin_url": data.get("linkedin_url"),
        "headquarters_location": data.get("headquarters_location"),
        "country": data.get("country"),
        "primary_vertical": data.get("primary_vertical"),
        "secondary_verticals": json.loads(data.get("secondary_verticals") or "[]"),
        "technologies": data.get("technologies"),
        "keywords": data.get("keywords"),
        "source": data.get("source"),
    }
    return payload

def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(QUERY)
    columns = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
    print(f"Found {len(rows)} startups to upload.")
    for i, row in enumerate(rows, 1):
        payload = row_to_payload(row, columns)
        try:
            resp = requests.post(API_URL, json=payload)
            if resp.status_code in (200, 201):
                print(f"[{i}/{len(rows)}] Uploaded: {payload['name']}")
            else:
                print(f"[{i}/{len(rows)}] Failed: {payload['name']} - {resp.status_code} {resp.text}")
        except Exception as e:
            print(f"[{i}/{len(rows)}] Error: {payload['name']} - {e}")
    conn.close()

if __name__ == "__main__":
    main()
