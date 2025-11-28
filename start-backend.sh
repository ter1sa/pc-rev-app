#!/bin/bash
# Run npm start for backend React frontend
npm start &

# Start the FastAPI server
uvicorn main:app --reload --port 8000
