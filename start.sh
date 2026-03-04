#!/bin/bash
# Startup script for Railway deployment

# Set working directory
cd /app || cd "$(dirname "$0")"

# Set Python path
export PYTHONPATH="$(pwd):${PYTHONPATH}"

# Cache ML models in the persistent volume so they survive redeploys
export SENTENCE_TRANSFORMERS_HOME="${SENTENCE_TRANSFORMERS_HOME:-/app/data/models}"
export TRANSFORMERS_CACHE="${TRANSFORMERS_CACHE:-/app/data/models}"
export HF_HOME="${HF_HOME:-/app/data/models}"

# Ensure model cache directory exists in the persistent volume
mkdir -p "$SENTENCE_TRANSFORMERS_HOME"

echo "======= DEPLOYMENT INFO ======="
echo "Working directory: $(pwd)"
echo "Python version: $(python --version)"
echo "Model cache: $SENTENCE_TRANSFORMERS_HOME"
echo "==============================="

# Initialize database and build search indexes
echo "Initializing database and search indexes..."
python init_railway.py || echo "Warning: Initialization failed — API will start with degraded search"
echo ""

# Start the API
exec python -m uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT:-8000}
