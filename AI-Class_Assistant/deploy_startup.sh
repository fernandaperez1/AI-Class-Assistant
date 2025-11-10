#!/bin/bash
set -e

echo "Cleaning up Docker resources..."
docker system prune -af

echo "Stopping Caddy service..."
sudo systemctl stop caddy || echo "⚠️ Caddy was not running"

echo "Rebuilding and starting containers..."
docker-compose up --build
