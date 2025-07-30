#!/bin/bash
# Start the FastAPI backend server

cd "$(dirname "$0")/backend"

echo "Starting PAF Site Editor Backend..."
echo "Installing dependencies..."
pip install -r requirements.txt

echo "Starting server on http://localhost:8000"
python main.py
