#!/bin/bash
# Run npm start for backend Node.js
npm start &

# Start the FastAPI server
uvicorn main:app --reload --port 8000
