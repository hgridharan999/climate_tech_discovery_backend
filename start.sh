#!/bin/bash
# Startup script for Railway deployment

# Set working directory
cd /app || cd "$(dirname "$0")"

# Set Python path to include current directory
export PYTHONPATH="$(pwd):${PYTHONPATH}"

# Debug: Print environment info
echo "Working directory: $(pwd)"
echo "PYTHONPATH: $PYTHONPATH"
echo "Python version: $(python --version)"
ls -la src/

# Run uvicorn
exec python -m uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT:-8000}
