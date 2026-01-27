# Next Steps: Populate Frontend with Real Startup Data

## 1. Setup PitchBook API Key

Create a `.env` file in the project root (copy from `.env.example`):

```bash
cp .env.example .env
```

Then edit `.env` and add your PitchBook sandbox API key:
```
PITCHBOOK_API_KEY=your_actual_sandbox_key_here
```

Get your sandbox key from the PitchBook API console.

## 2. Run the Scraper to Populate Database

Execute the scraper script to fetch real startup data:

```bash
python scripts/scrape_startups.py
```

This will:
- Scrape startups from Y Combinator (climate tag)
- Scrape startups from Climatebase
- Scrape startups from PitchBook (using sandbox for testing)
- Save all data to your SQLite database
- Display statistics of scraped data

## 3. Start the Backend API

Run the FastAPI server:

```bash
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at:
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## 4. Configure Frontend to Use Backend

In your frontend code, set the API base URL to point to your backend:

### React/Vue/Next.js Example:
```javascript
// In your API client or config file
const API_BASE_URL = 'http://localhost:8000';

// Example API call
async function searchStartups(query) {
  const response = await fetch(`${API_BASE_URL}/search?query=${encodeURIComponent(query)}`);
  return response.json();
}
```

### Environment Variable Approach:
```javascript
// .env.local (for Next.js/Vite)
VITE_API_BASE_URL=http://localhost:8000
// or
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000

// In your code
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL;
```

## 5. Test the Integration

### Test Backend Endpoints:

1. **Search startups:**
   ```bash
   curl "http://localhost:8000/search?query=solar%20energy&top_k=10"
   ```

2. **Get all startups:**
   ```bash
   curl "http://localhost:8000/startups?page=1&per_page=20"
   ```

3. **Get specific startup:**
   ```bash
   curl "http://localhost:8000/startups/1"
   ```

4. **Get statistics:**
   ```bash
   curl "http://localhost:8000/stats"
   ```

### Test from Frontend:
Once your frontend is configured, verify:
- Search functionality returns results
- Startup cards display correctly
- Filters work properly
- Pagination works

## 6. Production Deployment

When ready for production:

1. Switch from PitchBook sandbox to production API key
2. Deploy backend to Railway/Heroku/AWS
3. Update frontend API base URL to production backend URL
4. Enable CORS for your production frontend domain

## Available API Endpoints

- `GET /search` - Search startups (hybrid search with semantic + keyword)
- `GET /startups` - List all startups (paginated)
- `GET /startups/{id}` - Get single startup details
- `GET /stats` - Get database statistics
- `POST /startups` - Create new startup (admin)
- `PUT /startups/{id}` - Update startup (admin)

## Troubleshooting

- **No data returned:** Make sure you ran the scraper script first
- **CORS errors:** Check `ALLOWED_ORIGINS` in `.env` includes your frontend URL
- **PitchBook errors:** Verify your API key is correct and has sandbox access
- **Backend won't start:** Check all dependencies are installed with `pip install -r requirements.txt`
