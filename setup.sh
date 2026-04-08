#!/bin/bash
set -e

echo "🔥 FireWatch — Setup Script"
echo "================================"

# Check docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Please install Docker first."
    exit 1
fi

if ! command -v docker compose &> /dev/null && ! docker compose version &> /dev/null 2>&1; then
    echo "❌ Docker Compose not found."
    exit 1
fi

# Check for model
MODEL_PATH="./backend/models/yolo8m.pt"
mkdir -p ./backend/models

if [ ! -f "$MODEL_PATH" ]; then
    echo ""
    echo "⚠️  Model file not found at: $MODEL_PATH"
    echo ""
    echo "Please copy your yolo8m.pt model:"
    echo "  cp /path/to/yolo8m.pt ./backend/models/yolo8m.pt"
    echo ""
    echo "The app will run in DEMO MODE without the model."
    echo ""
fi

# Create temp directory
mkdir -p ./backend/temp

echo "🚀 Starting services with Docker Compose..."
docker compose up --build -d

echo ""
echo "⏳ Waiting for services to be healthy..."
sleep 15

echo ""
echo "✅ FireWatch is running!"
echo ""
echo "  🌐 Web Interface:    http://localhost:3000"
echo "  📚 API Docs:         http://localhost:8000/docs"
echo "  🗄️  MinIO Console:    http://localhost:9001"
echo "       Login: minioadmin / minioadmin123"
echo ""
echo "To stop: docker compose down"
echo "To view logs: docker compose logs -f"
