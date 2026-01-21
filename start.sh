#!/bin/bash
# Startup script for Railway deployment

# Set Python path to include the app directory
export PYTHONPATH="${PYTHONPATH}:/app"

# Run uvicorn using Python module syntax
exec python -m uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT:-8000}
