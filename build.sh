#!/usr/bin/env bash
# Exit on error
set -o errexit

# Install Python backend dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Install frontend dependencies and build Vite static files
cd frontend
npm install
npm run build
cd ..
