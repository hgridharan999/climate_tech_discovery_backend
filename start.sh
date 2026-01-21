#!/bin/bash
# Startup script for Railway deployment

# Set working directory
cd /app || cd "$(dirname "$0")"

# Set Python path to include current directory
export PYTHONPATH="$(pwd):${PYTHONPATH}"

# Debug: Print environment info
echo "======= DEPLOYMENT DEBUG INFO ======="
echo "Working directory: $(pwd)"
echo "PYTHONPATH: $PYTHONPATH"
echo "Python version: $(python --version)"
echo ""
echo "Contents of src/:"
ls -la src/
echo ""
echo "Checking for src/data/:"
if [ -d "src/data" ]; then
    echo "✓ src/data EXISTS"
    ls -la src/data/
else
    echo "✗ src/data MISSING!"
fi
echo "====================================="
echo ""

# Initialize database if needed
echo "Initializing database..."
python init_railway.py || echo "Warning: Database initialization failed"
echo ""

# Run uvicorn
exec python -m uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT:-8000}
