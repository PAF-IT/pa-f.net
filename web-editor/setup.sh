#!/bin/bash
# Setup script for PAF Site Editor

set -e  # Exit on any error

echo "=== PAF Site Editor Setup ==="
echo

# Check if we're in the right directory
if [ ! -f "../sitemap.json" ]; then
    echo "Warning: sitemap.json not found in parent directory."
    echo "Make sure to run the palimpsest parser first to generate sitemap.json"
    echo
fi

# Setup backend
echo "1. Setting up backend..."
cd backend
echo "   Installing Python dependencies..."
pip install -r requirements.txt
echo "   ✓ Backend dependencies installed"
cd ..

# Setup frontend
echo
echo "2. Setting up frontend..."
cd frontend
echo "   Installing Node.js dependencies..."
npm install
echo "   ✓ Frontend dependencies installed"
cd ..

echo
echo "=== Setup Complete! ==="
echo
echo "To start the application:"
echo "1. Start backend:  ./start-backend.sh"
echo "2. Start frontend: ./start-frontend.sh"
echo "3. Open http://localhost:3000 in your browser"
echo
echo "Make sure you have a sitemap.json file in the project root first!"
