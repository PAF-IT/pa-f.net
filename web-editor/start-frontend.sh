#!/bin/bash
# Start the React frontend development server

cd "$(dirname "$0")/frontend"

echo "Starting PAF Site Editor Frontend..."
echo "Installing dependencies..."
npm install

echo "Starting development server on http://localhost:3000"
npm run dev
