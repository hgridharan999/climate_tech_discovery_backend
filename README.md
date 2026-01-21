# Climate Tech Search API

AI-powered search engine for climate technology startups using hybrid semantic and keyword search.

## Features

- **Hybrid Search**: Combines BERT-based semantic search (FAISS) with BM25 keyword search
- **Reciprocal Rank Fusion**: Optimal combination of search results
- **Query Expansion**: Automatic synonym expansion for better recall
- **Result Diversification**: Ensures variety across climate verticals
- **12 Climate Verticals**: Carbon Management, Clean Energy, Energy Storage, and more
- **Evaluation Framework**: NDCG@10 and other IR metrics

## Quick Start

### 1. Install dependencies

```bash
cd climate-search-api
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your settings (optional for basic usage)
```

### 3. Initialize database and generate sample data

```bash
python scripts/initial_setup.py
```

### 4. Build search indexes

```bash
python scripts/rebuild_index.py
```

### 5. Start the API server

```bash
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```

## API Endpoints

### Search

```bash
# POST search
curl -X POST "http://localhost:8000/api/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "solar energy startup", "top_k": 10}'

# GET search
curl "http://localhost:8000/api/search?q=carbon+capture&top_k=10"
```

### Startups

```bash
# Get startup by ID
curl "http://localhost:8000/api/startups/1"

# List startups by vertical
curl "http://localhost:8000/api/startups?vertical=clean_energy&limit=20"
```

### Verticals

```bash
curl "http://localhost:8000/api/verticals"
```

### Statistics

```bash
curl "http://localhost:8000/api/stats"
```

### Health Check

```bash
curl "http://localhost:8000/health"
```

### Evaluation

```bash
curl "http://localhost:8000/api/evaluate"
```

## Climate Verticals

1. Carbon Management
2. Clean Energy
3. Energy Storage
4. Green Transportation
5. Sustainable Agriculture
6. Built Environment
7. Circular Economy
8. Climate Fintech
9. Water & Ocean
10. Industrial Decarbonization
11. Climate Adaptation
12. Grid & Energy Management

## Search Features

### Query Expansion

Queries are automatically expanded with climate-specific synonyms:
- "solar" → "solar photovoltaic PV solar panel solar energy"
- "EV" → "EV electric vehicle electric car e-mobility"

### Filters

```json
{
  "query": "battery storage",
  "vertical_filter": "energy_storage",
  "founded_year_min": 2015,
  "founded_year_max": 2024,
  "min_funding_usd": 1000000
}
```

### Result Diversification

By default, results are diversified to show a maximum of 3 startups per vertical, ensuring variety in search results.

## Project Structure

```
climate-search-api/
├── src/
│   ├── api/              # FastAPI application
│   │   ├── main.py       # App entry point
│   │   ├── models.py     # Pydantic schemas
│   │   └── routes/       # API endpoints
│   ├── core/             # Core utilities
│   │   ├── config.py     # Settings management
│   │   ├── database.py   # SQLite with FTS5
│   │   └── logging.py    # Logging setup
│   ├── search/           # Search engines
│   │   ├── embedder.py   # BERT embeddings
│   │   ├── faiss_manager.py
│   │   ├── bm25_engine.py
│   │   ├── hybrid_search.py
│   │   ├── query_processor.py
│   │   └── diversifier.py
│   ├── evaluation/       # IR metrics
│   │   └── evaluator.py
│   └── data/             # Data scraping
│       ├── scraper.py
│       └── category_mapper.py
├── scripts/
│   ├── initial_setup.py
│   └── rebuild_index.py
├── config/
│   ├── climate_taxonomy.json
│   └── test_queries.json
├── requirements.txt
└── README.md
```

## Development

### Run tests

```bash
pytest tests/
```

### Format code

```bash
black src/ scripts/
ruff check src/ scripts/
```

## Performance

- Search latency: <500ms (P95)
- Memory usage: ~2-4GB for embeddings
- Index rebuild: ~5-10 minutes for 10K startups

## License

MIT
