# AI Class Assistant - Useful Commands & Instructions

## Docker Commands

### Start All Services
```bash
# Start all containers (frontend, backend, bot, database)
docker-compose up

# Start in background (detached mode)
docker-compose up -d

# Rebuild and start (use after code changes)
docker-compose up --build

# Rebuild specific service
docker-compose up --build -d backend
docker-compose up --build -d bot
docker-compose up --build -d frontend
```

### Stop Services
```bash
# Stop all containers
docker-compose down

# Stop and remove volumes (WARNING: deletes database data)
docker-compose down -v
```

### Check Service Status
```bash
# View all running containers
docker-compose ps

# Check specific service
docker-compose ps backend
docker-compose ps bot
docker-compose ps frontend
docker-compose ps db
```

### Restart Services
```bash
# Restart all services
docker-compose restart

# Restart specific service
docker-compose restart backend
docker-compose restart bot
docker-compose restart frontend
docker-compose restart db
```

## 📋 View Logs

### Backend Logs
```bash
# View all backend logs
docker logs class_backend

# View last 50 lines
docker logs class_backend --tail=50

# Follow logs in real-time
docker logs class_backend -f

# View logs with timestamps
docker logs class_backend -t
```

### Bot Logs
```bash
# View all bot logs
docker logs class_bot

# View last 50 lines
docker logs class_bot --tail=50

# Follow logs in real-time
docker logs class_bot -f

# View both stdout and stderr
docker logs class_bot 2>&1 | tail -30
```

### Frontend Logs
```bash
# View all frontend logs
docker logs class_frontend

# View last 50 lines
docker logs class_frontend --tail=50

# Follow logs in real-time
docker logs class_frontend -f
```

### Database Logs
```bash
# View database logs
docker logs class_db

# View last 50 lines
docker logs class_db --tail=50

# Follow logs in real-time
docker logs class_db -f
```

### View All Logs
```bash
# View logs from all services
docker-compose logs

# Follow all logs in real-time
docker-compose logs -f

# View last 50 lines from all services
docker-compose logs --tail=50

# View logs for specific service
docker-compose logs backend
docker-compose logs bot
```

## 🗄️ Database Commands

### Access Database
```bash
# Access PostgreSQL from inside the container
docker-compose exec db psql -U postgres -d class_assistant

# Or using docker directly
docker exec -it class_db psql -U postgres -d class_assistant
```

### Reset Database
```bash
# Method 1: Use the reset script (RECOMMENDED)
docker-compose exec backend python db/reset_db.py

# Method 2: Drop and recreate manually
docker-compose exec db psql -U postgres -c "DROP DATABASE IF EXISTS class_assistant;"
docker-compose exec db psql -U postgres -c "CREATE DATABASE class_assistant;"
docker-compose exec db psql -U postgres -d class_assistant -f /docker-entrypoint-initdb.d/init.sql
```

### View Database Tables
```bash
# List all tables
docker-compose exec db psql -U postgres -d class_assistant -c "\dt"

# Describe table structure
docker-compose exec db psql -U postgres -d class_assistant -c "\d users"
docker-compose exec db psql -U postgres -d class_assistant -c "\d classes"
docker-compose exec db psql -U postgres -d class_assistant -c "\d presentations"
```

### Query Database
```bash
# View all users
docker-compose exec db psql -U postgres -d class_assistant -c "SELECT * FROM users;"

# View user with Telegram info
docker-compose exec db psql -U postgres -d class_assistant -c "SELECT id, email, telegram_chat_id, telegram_link_code FROM users;"

# View all classes
docker-compose exec db psql -U postgres -d class_assistant -c "SELECT * FROM classes;"

# View all presentations
docker-compose exec db psql -U postgres -d class_assistant -c "SELECT * FROM presentations;"

# Count records
docker-compose exec db psql -U postgres -d class_assistant -c "SELECT COUNT(*) FROM users;"
```

### Backup Database
```bash
# Create backup
docker-compose exec db pg_dump -U postgres class_assistant > backup.sql

# Restore from backup
docker-compose exec -T db psql -U postgres -d class_assistant < backup.sql
```

## 🔧 Development Commands

### Backend Development
```bash
# Enter backend container shell
docker-compose exec backend bash

# Install new Python package
docker-compose exec backend pip install package-name

# Run Python script
docker-compose exec backend python script.py

# Check Python version
docker-compose exec backend python --version

# List installed packages
docker-compose exec backend pip list
```

### Frontend Development
```bash
# Enter frontend container shell
docker-compose exec frontend sh

# Install new npm package
docker-compose exec frontend yarn add package-name

# Check Node version
docker-compose exec frontend node --version

# Check Yarn version
docker-compose exec frontend yarn --version
```

### Bot Development
```bash
# Enter bot container shell
docker-compose exec bot bash

# Install new Python package
docker-compose exec bot pip install package-name

# Run bot script directly
docker-compose exec bot python bot.py
```

## 🧹 Cleanup Commands

### Remove Containers
```bash
# Stop and remove all containers
docker-compose down

# Remove containers and volumes (WARNING: deletes data)
docker-compose down -v

# Remove containers, volumes, and images
docker-compose down -v --rmi all
```

### Clean Docker System
```bash
# Remove unused containers
docker container prune

# Remove unused images
docker image prune

# Remove unused volumes
docker volume prune

# Clean everything (use with caution)
docker system prune -a
```

## 🌐 Access URLs

- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:5000
- **Database**: localhost:5432
  - Username: `postgres`
  - Password: `postgres`
  - Database: `class_assistant`

## 🔍 Debugging Commands

### Check Container Resources
```bash
# View container stats (CPU, Memory, etc.)
docker stats

# View stats for specific container
docker stats class_backend
```

### Inspect Containers
```bash
# Inspect container configuration
docker inspect class_backend
docker inspect class_bot
docker inspect class_db
```

### Network Debugging
```bash
# List Docker networks
docker network ls

# Inspect network
docker network inspect ai-class_assistant_default

# Test connectivity between containers
docker-compose exec backend ping db
docker-compose exec backend ping frontend
```

### File System Access
```bash
# Copy file from container to host
docker cp class_backend:/app/file.txt ./file.txt

# Copy file from host to container
docker cp ./file.txt class_backend:/app/file.txt

# List files in container
docker-compose exec backend ls -la /app
```

## 🚀 Quick Start Workflow

### First Time Setup
```bash
# 1. Build and start all services
docker-compose up --build

# 2. Check if all services are running
docker-compose ps

# 3. View database tables to verify initialization
docker-compose exec db psql -U postgres -d class_assistant -c "\dt"

# 4. Access the frontend
# Open browser: http://localhost:5173
```

### Daily Development
```bash
# Start services
docker-compose up -d

# View logs to check for errors
docker-compose logs -f

# Make code changes (auto-reload for frontend/backend)

# Restart specific service if needed
docker-compose restart backend

# Stop when done
docker-compose down
```

### After Code Changes
```bash
# Backend/Bot changes - rebuild
docker-compose up --build -d backend bot

# Frontend changes - usually auto-reloads, but if needed:
docker-compose restart frontend

# View logs to verify
docker-compose logs backend bot frontend --tail=20
```

## 🐛 Common Issues & Solutions

### Issue: Port Already in Use
```bash
# Find process using port 5000
lsof -i :5000
# Kill process
kill -9 <PID>

# Or change port in docker-compose.yml
```

### Issue: Database Connection Refused
```bash
# Check if database is running
docker-compose ps db

# Restart database
docker-compose restart db

# Check database logs
docker logs class_db --tail=50
```

### Issue: Bot Not Responding
```bash
# Check bot logs for errors
docker logs class_bot --tail=50

# Restart bot
docker-compose restart bot

# Check if bot token is set
docker-compose exec bot env | grep TELEGRAM_TOKEN
```

### Issue: Frontend Not Loading
```bash
# Check frontend logs
docker logs class_frontend --tail=50

# Rebuild frontend
docker-compose up --build -d frontend

# Check if running on correct port
docker-compose ps frontend
```

## 📝 Environment Variables

### View Environment Variables
```bash
# Backend environment
docker-compose exec backend env

# Bot environment
docker-compose exec bot env

# Frontend environment
docker-compose exec frontend env
```

### Update Environment Variables
1. Edit `.env` file in the respective directory
2. Restart the service:
   ```bash
   docker-compose restart backend
   docker-compose restart bot
   ```

## 🧪 Testing Commands

### Test Database Connection
```bash
# From backend
docker-compose exec backend python -c "from db.database import get_db_cursor; print('DB Connection OK')"
```

### Test API Endpoints
```bash
# Test backend health
curl http://localhost:5000/

# Test user endpoint (replace with actual Firebase UID)
curl http://localhost:5000/api/users/your-firebase-uid
```

### Test Telegram Bot
```bash
# Check if bot is receiving updates
docker logs class_bot -f

# Send message to bot and watch logs
```

## 📚 Additional Resources

- **Database Schema**: See `backend/db/init.sql`
- **API Documentation**: See `backend/app.py` for all endpoints
- **Bot Commands**: See `bot/bot.py` for available commands
- **Architecture**: See `ARCHITECTURE_FLOW.md`
- **Firebase Setup**: See `FIREBASE_AUTH_SETUP.md`
- **Getting Started**: See `GETTING_STARTED.md`