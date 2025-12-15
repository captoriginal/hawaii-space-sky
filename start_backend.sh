#!/bin/bash

# Start the Hawaii Space Sky backend server

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Start the backend using uvicorn
# The FastAPI app is in backend/app/main.py with the app instance named 'app'
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
