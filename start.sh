#!/bin/bash
# Startup script for Railway deployment

# Change to the app directory
cd /app

# Set Python path to include the app directory
export PYTHONPATH="/app:${PYTHONPATH}"

# Run uvicorn using Python module syntax
exec python -m uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT:-8000}
