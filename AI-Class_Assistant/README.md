# AI Class Assistant

An intelligent teaching assistant platform that enhances classroom presentations with AI-powered features including real-time question generation, interactive examples, and Telegram bot integration for student engagement.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [How to Use](#how-to-use)
- [Architecture](#architecture)
- [Local Development Setup](#local-development-setup)
- [Production Deployment](#production-deployment)
- [Environment Variables](#environment-variables)
- [Troubleshooting](#troubleshooting)
- [Additional Documentation](#additional-documentation)

## Overview

AI Class Assistant is a full-stack application designed to help educators create more engaging and interactive presentations. It uses AI (Google Gemini) to automatically generate quiz questions, examples, and educational content based on uploaded PowerPoint presentations. Students can interact with the system through a Telegram bot, receiving real-time updates and participating in class activities.

### Key Components

- **Frontend**: React + Vite web application with Firebase authentication
- **Backend**: Flask REST API with Socket.IO for real-time communication
- **Bot**: Telegram bot for student interaction and notifications
- **Database**: PostgreSQL for data persistence
- **Nginx**: Reverse proxy with SSL/TLS support
- **Certbot**: Automated SSL certificate management

## Features

### For Educators
- **Presentation Management**: Upload and manage PowerPoint presentations
- **AI Question Generation**: Automatically create multiple-choice and open-ended questions
- **AI Examples**: Generate relevant real-world examples for any slide
- **Dynamic Slide Insertion**: Add AI-generated content directly into presentations
- **Real-time Updates**: Live synchronization with students via WebSockets
- **Telegram Integration**: Send notifications and updates to students instantly

### For Students
- **Telegram Bot**: Receive class updates, questions, and materials
- **Easy Registration**: Link Telegram account to web platform with simple code
- **Push Notifications**: Get instant alerts for new content and questions
- **Interactive Learning**: Engage with AI-generated questions and examples

### Technical Features
- **Firebase Authentication**: Secure user management
- **Real-time Communication**: Socket.IO for live updates
- **Docker Containerization**: Easy deployment and scaling
- **HTTPS Support**: Production-ready SSL/TLS configuration
- **Multi-service Architecture**: Microservices-based design

## How to Use

### Initial Setup (First Time)

1. **Register an Account**
   - Visit the web application (local: `http://localhost:5173`, production: `https://tutorflow.duckdns.org`)
   - Sign up using email or Google authentication
   - Complete your profile setup

2. **Link Your Telegram Account** (Optional but Recommended)
   - Start a chat with the Telegram bot: [@TutorFlowBot](https://t.me/TutorFlowBot)
   - Send `/start` to the bot
   - The bot will provide a 6-digit linking code
   - Enter this code in the web application under "Settings" or "Telegram Integration"
   - Your Telegram account is now linked!

### Creating and Managing Classes

1. **Create a New Class**
   - Click "Create Class" on the home page
   - Enter class name, description, and optional details

2. **Upload a Presentation**
   - Click "Upload Presentation" when creating the class
   - Select a PowerPoint (.pptx) file
   - Wait for the upload and processing to complete
   - The presentation will be parsed and stored

### Using AI Features

#### Generate Questions

1. Navigate to your presentation
2. Select a slide where you want to insert a question
3. Click "Generate Question" or "Generate Multiple Choice"
4. (Optional) Provide additional context or specify the question type
5. The AI will generate 3 question variations
6. Select your preferred question
7. The question will be inserted into your presentation after the selected slide

#### Generate Examples

1. Select a slide that needs a practical example
2. Click "Generate Example"
3. (Optional) Provide context about what kind of example you need
4. The AI will create a relevant real-world example
5. Review and insert the example into your presentation

### Managing Presentations

- **View Slides**: Browse through all slides in a presentation
- **Download Modified Presentations**: Export your enhanced presentation with AI-generated content

## Architecture

```
┌─────────────────┐      ┌──────────────────┐      ┌─────────────────┐
│                 │      │                  │      │                 │
│  React Frontend │◄────►│  Nginx (Reverse  │◄────►│  Flask Backend  │
│   (Port 5173)   │      │      Proxy)      │      │   (Port 5000)   │
│                 │      │  (Ports 80/443)  │      │                 │
└─────────────────┘      └──────────────────┘      └─────────┬───────┘
                                                             │
                         ┌──────────────────┐                │
                         │                  │                │
                         │  PostgreSQL DB   │◄───────────────┤
                         │   (Port 5432)    │                │
                         │                  │                │
                         └──────────────────┘                │
                                                             │
                         ┌──────────────────┐                │
                         │                  │                │
                         │  Telegram Bot    │◄───────────────┘
                         │  (Websockets)    │
                         │                  │
                         └──────────────────┘
```

### Service Communication

- **Frontend ↔ Backend**: REST API + Socket.IO WebSockets
- **Backend ↔ Database**: PostgreSQL connection via psycopg2
- **Backend ↔ Bot**: HTTP requests + WebSocket events
- **Bot ↔ Telegram**: Telegram Bot API
- **Backend ↔ AI**: Google Gemini API

## Local Development Setup

### Prerequisites

- Docker and Docker Compose installed
- Git
- (Optional) Node.js 20+ and Python 3.11+ for local development without Docker

### Step 1: Clone the Repository

```bash
git clone <repository-url>
cd AI-Class_Assistant
```

### Step 2: Configure Environment Variables

Create `.env` files for each service:

#### Backend (`backend/.env`)

```env
# Flask Configuration
FLASK_ENV=development
FLASK_DEBUG=1

# Database
DATABASE_URL=postgresql://postgres:postgres@db:5432/class_assistant

# CORS (allow frontend access)
CORS_ORIGINS=http://localhost:5173

# File Upload
MAX_CONTENT_LENGTH=104857600  # 100MB
UPLOAD_FOLDER=uploads

# AI Provider - Choose 'gemini' or 'openai'
AI_PROVIDER=gemini

# AI API Keys (only need the one matching AI_PROVIDER)
GOOGLE_API_KEY=your_google_gemini_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
```

#### Frontend (`frontend/.env`)

```env
VITE_API_URL=http://localhost:5000

# Firebase Configuration
VITE_FIREBASE_API_KEY=your_firebase_api_key
VITE_FIREBASE_AUTH_DOMAIN=your_project.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=your_project_id
VITE_FIREBASE_STORAGE_BUCKET=your_project.appspot.com
VITE_FIREBASE_MESSAGING_SENDER_ID=your_sender_id
VITE_FIREBASE_APP_ID=your_app_id
```

#### Bot (`bot/.env`)

```env
TELEGRAM_TOKEN=your_telegram_bot_token_from_botfather
BACKEND_URL=http://backend:5000
```

**Where to get API keys:**
- **Google Gemini API**: [Google AI Studio](https://aistudio.google.com/apikey) (free tier available)
- **OpenAI API**: [OpenAI Platform](https://platform.openai.com/api-keys) (requires payment)
- **Firebase**: [Firebase Console](https://console.firebase.google.com/) → Create project → Project settings
- **Telegram Bot Token**: Chat with [@BotFather](https://t.me/botfather) on Telegram → `/newbot`

**Note**: You only need one AI API key (either Gemini or OpenAI) based on your `AI_PROVIDER` setting. Gemini is recommended for getting started as it has a free tier.

### Step 3: Create docker-compose.override.yml

For local development, create this file to avoid port conflicts:

```yaml
services:
  frontend:
    ports:
      - "5173:5173"

  nginx:
    ports:
      - "8080:80"
      - "8443:443"
```

This file is automatically used by Docker Compose and should be in `.gitignore`.

### Step 4: Start the Application

```bash
# Start all services (frontend, backend, database, bot)
docker compose up frontend backend db bot

# Or run in detached mode
docker compose up -d frontend backend db bot

# View logs
docker compose logs -f
```

### Step 5: Access the Application

- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:5000
- **Database**: localhost:5432 (user: `postgres`, password: `postgres`, db: `class_assistant`)

### Development Workflow

#### Making Code Changes

- **Frontend**: Changes auto-reload via Vite HMR
- **Backend**: Changes auto-reload via Flask debug mode (if volumes are mounted)
- **Bot**: Restart required: `docker compose restart bot`

#### Viewing Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f backend
docker compose logs -f bot
docker compose logs -f frontend

# Last 50 lines
docker compose logs --tail=50 backend
```

#### Database Management

```bash
# Access PostgreSQL shell
docker compose exec db psql -U postgres -d class_assistant

# Reset database (WARNING: deletes all data)
docker compose exec backend python db/reset_db.py

# View tables
docker compose exec db psql -U postgres -d class_assistant -c "\dt"
```

#### Rebuilding After Changes

```bash
# Rebuild specific service
docker compose up --build backend
docker compose up --build bot

# Rebuild all
docker compose up --build
```

#### Stopping Services

```bash
# Stop all containers
docker compose down

# Stop and remove volumes (deletes database data)
docker compose down -v
```

## 🌐 Production Deployment

### Prerequisites

- Ubuntu/Debian server (EC2, DigitalOcean, etc.)
- Domain name or DuckDNS subdomain
- Docker and Docker Compose installed on server
- Ports 80, 443, and optionally 5000 open in firewall/security groups

### Step 1: Server Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo apt install docker-compose-plugin -y

# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker
```

### Step 2: Configure Domain

#### Option A: DuckDNS (Free)

1. Visit [DuckDNS.org](https://www.duckdns.org/)
2. Sign in and create a subdomain (e.g., `yourapp.duckdns.org`)
3. Point it to your server's IP address
4. Set up auto-update (optional):

```bash
# Add to crontab
echo "*/5 * * * * curl https://www.duckdns.org/update?domains=yourapp&token=YOUR_TOKEN" | crontab -
```

#### Option B: Custom Domain

1. Add an A record pointing to your server's IP
2. Wait for DNS propagation (can take up to 48 hours)

### Step 3: Clone and Configure

```bash
# Clone repository
git clone <repository-url>
cd AI-Class_Assistant

# Create production environment files
# Edit backend/.env with production values:
nano backend/.env
```

**Production backend/.env:**

```env
FLASK_ENV=production
FLASK_DEBUG=0
DATABASE_URL=postgresql://postgres:postgres@db:5432/class_assistant
CORS_ORIGINS=https://yourapp.duckdns.org,http://yourapp.duckdns.org
GOOGLE_API_KEY=your_production_api_key
MAX_CONTENT_LENGTH=104857600
UPLOAD_FOLDER=uploads
```

**Production frontend/.env:**

```env
VITE_API_URL=https://yourapp.duckdns.org
# ... Firebase config (same as local)
```

### Step 4: Configure Nginx

The `nginx/nginx.conf` should already be configured for HTTPS. Verify the domain name:

```bash
nano nginx/nginx.conf
```

Ensure `server_name` matches your domain:

```nginx
server_name yourapp.duckdns.org;
```

### Step 5: SSL Certificate Setup

#### Initial HTTP-only start (for certificate generation)

1. Temporarily use HTTP-only config:

```bash
# Backup main config
cp nginx/nginx.conf nginx/nginx.conf.backup

# Use HTTP-only config (if you have one)
cp nginx/nginx-http-only.conf nginx/nginx.conf
```

2. Start nginx:

```bash
docker compose up -d nginx
```

3. Generate SSL certificate:

```bash
docker compose run --rm certbot certonly --webroot \
  --webroot-path=/var/www/certbot \
  --email your-email@example.com \
  --agree-tos \
  --no-eff-email \
  -d yourapp.duckdns.org
```

4. Restore HTTPS config:

```bash
cp nginx/nginx.conf.backup nginx/nginx.conf
docker compose restart nginx
```

### Step 6: Start All Services

```bash
# Start all services in production mode
docker compose up -d

# Check status
docker compose ps

# View logs
docker compose logs -f
```

### Step 7: Verify Deployment

1. Visit `https://yourapp.duckdns.org`
2. Check SSL certificate (should be valid)
3. Test signup/login
4. Test Telegram bot
5. Upload a test presentation

### Security Considerations

1. **Firewall Configuration** (AWS Security Groups / UFW):

```bash
# Allow SSH, HTTP, HTTPS
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

2. **Environment Variables**: Never commit `.env` files. Ensure they're in `.gitignore`

3. **Database Passwords**: Change default PostgreSQL password in production:

```yaml
# docker-compose.yml
environment:
  POSTGRES_PASSWORD: strong_random_password_here
```

4. **SSL/TLS**: Certbot auto-renewal runs every 12 hours via the certbot container

5. **CORS**: Restrict CORS_ORIGINS to your production domain only

### Monitoring and Maintenance

```bash
# View all container logs
docker compose logs -f

# Check container health
docker compose ps

# Restart specific service
docker compose restart backend

# Update application
git pull
docker compose up --build -d

# Backup database
docker compose exec db pg_dump -U postgres class_assistant > backup_$(date +%Y%m%d).sql

# Restore database
docker compose exec -T db psql -U postgres class_assistant < backup_20250109.sql
```

### Updating the Application

```bash
# Pull latest changes
git pull origin main

# Rebuild and restart
docker compose up --build -d

# Check logs for errors
docker compose logs -f
```

## 🔧 Environment Variables

### Backend Environment Variables

| Variable | Description | Example | Required |
|----------|-------------|---------|----------|
| `FLASK_ENV` | Flask environment | `development` or `production` | Yes |
| `FLASK_DEBUG` | Enable debug mode | `1` or `0` | Yes |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:pass@host:5432/db` | Yes |
| `CORS_ORIGINS` | Allowed CORS origins (comma-separated) | `http://localhost:5173,https://app.com` | Yes |
| `AI_PROVIDER` | AI model provider to use | `gemini` or `openai` | Yes |
| `GOOGLE_API_KEY` | Google Gemini API key (if using Gemini) | `AIza...` | Conditional* |
| `OPENAI_API_KEY` | OpenAI API key (if using OpenAI) | `sk-...` | Conditional* |
| `MAX_CONTENT_LENGTH` | Max upload size in bytes | `104857600` (100MB) | No |
| `UPLOAD_FOLDER` | Upload directory path | `uploads` | No |

**\*Note**: Only the API key matching your `AI_PROVIDER` choice is required. For example, if `AI_PROVIDER=gemini`, you only need `GOOGLE_API_KEY`.

#### AI Provider Configuration

The application supports two AI providers for generating questions, examples, and summaries:

**Gemini (Google)**
- Model: `gemini-2.0-flash-exp`
- Best for: Fast responses, experimental reasoning features
- Get API key: [Google AI Studio](https://aistudio.google.com/apikey)

**OpenAI**
- Model: `gpt-4o`
- Best for: High-quality, consistent outputs
- Get API key: [OpenAI Platform](https://platform.openai.com/api-keys)

To switch providers, update `AI_PROVIDER` in `backend/.env` and restart the backend container:

```bash
# In backend/.env
AI_PROVIDER=openai  # or 'gemini'
OPENAI_API_KEY=sk-your-key-here

# Restart backend
docker compose restart backend
```

### Frontend Environment Variables

| Variable | Description | Example | Required |
|----------|-------------|---------|----------|
| `VITE_API_URL` | Backend API URL | `http://localhost:5000` | Yes |
| `VITE_FIREBASE_API_KEY` | Firebase API key | `AIza...` | Yes |
| `VITE_FIREBASE_AUTH_DOMAIN` | Firebase auth domain | `project.firebaseapp.com` | Yes |
| `VITE_FIREBASE_PROJECT_ID` | Firebase project ID | `my-project-123` | Yes |
| `VITE_FIREBASE_STORAGE_BUCKET` | Firebase storage bucket | `project.appspot.com` | Yes |
| `VITE_FIREBASE_MESSAGING_SENDER_ID` | Firebase sender ID | `123456789` | Yes |
| `VITE_FIREBASE_APP_ID` | Firebase app ID | `1:123:web:abc` | Yes |

### Bot Environment Variables

| Variable | Description | Example | Required |
|----------|-------------|---------|----------|
| `TELEGRAM_TOKEN` | Telegram bot token from BotFather | `123456:ABC-DEF...` | Yes |
| `BACKEND_URL` | Backend API URL | `http://backend:5000` | Yes |

## 🐛 Troubleshooting

### Common Issues

#### Port Already in Use

**Error**: `Bind for 0.0.0.0:5000 failed: port is already allocated`

**Solution**:
```bash
# Find process using the port
lsof -i :5000
# Or on Linux
sudo netstat -tulpn | grep :5000

# Kill the process
kill -9 <PID>

# Or use docker-compose.override.yml to change port
```

#### Frontend Refuses to Connect

**Error**: Connection refused when accessing `http://localhost:5173`

**Solution**:
1. Ensure `docker-compose.override.yml` exists with frontend port mapping
2. Restart frontend: `docker compose up -d frontend`
3. Check logs: `docker compose logs frontend`

#### CORS Errors

**Error**: `Origin http://localhost:5173 is not allowed by Access-Control-Allow-Origin`

**Solution**:
1. Add origin to `backend/.env`: `CORS_ORIGINS=http://localhost:5173`
2. Restart backend: `docker compose restart backend`

#### WebSocket Connection Failed

**Error**: `WebSocket connection to 'ws://localhost:5000/socket.io/' failed`

**Solution**:
1. Verify backend is running: `docker compose ps backend`
2. Check CORS_ORIGINS includes frontend URL
3. Restart backend to reload env vars: `docker compose restart backend`

#### Vite Host Blocking

**Error**: `[vite] Blocked request. This host (tutorflow.duckdns.org) is not allowed`

**Solution**:
Edit `frontend/vite.config.js`:
```javascript
export default defineConfig({
  server: {
    host: '0.0.0.0',
    port: 5173,
    allowedHosts: ['localhost', 'tutorflow.duckdns.org', 'your-domain.com']
  }
})
```

#### Database Connection Refused

**Error**: `psycopg2.OperationalError: could not connect to server`

**Solution**:
```bash
# Check database status
docker compose ps db

# Restart database
docker compose restart db

# Check database logs
docker compose logs db

# Verify connection string in backend/.env
```

#### Slide Layout Index Out of Range

**Error**: `IndexError: slide layout index out of range`

**Solution**:
This has been fixed in the code. The `add_slide()` function now dynamically detects available layouts. Ensure you're running the latest code:
```bash
git pull
docker compose restart backend
```

#### Telegram Bot Not Responding

**Error**: Bot doesn't reply to messages

**Solution**:
1. Verify bot token is correct: Check `bot/.env`
2. Check bot logs: `docker compose logs bot`
3. Test bot webhook: Send `/start` to the bot
4. Restart bot: `docker compose restart bot`

#### SSL Certificate Errors

**Error**: Certificate not valid or expired

**Solution**:
```bash
# Check certificate expiration
docker compose exec nginx openssl x509 -in /etc/letsencrypt/live/yourapp.duckdns.org/fullchain.pem -noout -dates

# Manually renew
docker compose run --rm certbot renew

# Restart nginx
docker compose restart nginx
```

### Getting Help

1. **Check Logs**: Always start by checking service logs
   ```bash
   docker compose logs -f [service-name]
   ```

2. **Verify Environment**: Ensure all `.env` files are properly configured
   ```bash
   docker compose exec backend env | grep -E "DATABASE|CORS|GOOGLE"
   ```

3. **Container Status**: Check if all containers are running
   ```bash
   docker compose ps
   ```

4. **Network Connectivity**: Test inter-container communication
   ```bash
   docker compose exec backend ping db
   docker compose exec bot curl http://backend:5000
   ```

5. **Database State**: Verify database tables exist
   ```bash
   docker compose exec db psql -U postgres -d class_assistant -c "\dt"
   ```

## Additional Documentation

- **[instructions.md](instructions.md)**: Detailed Docker commands and workflows
- **[docker_considerations.md](docker_considerations.md)**: Local development setup guide
- **Backend API**: See `backend/app.py` for all endpoints
- **Database Schema**: See `backend/db/init.sql` for table structures
- **Bot Commands**: See `bot/bot.py` for available Telegram commands

## Tech Stack

### Frontend
- React 18
- Vite 5
- Socket.IO Client
- Firebase Authentication
- React Router
- Reveal.js (presentation viewer)
- PDF.js (PDF processing)

### Backend
- Flask
- Flask-SocketIO
- Flask-CORS
- python-pptx (PowerPoint processing)
- psycopg2 (PostgreSQL driver)
- Google Gemini AI
- python-dotenv

### Bot
- python-telegram-bot 20.6
- Vosk (speech recognition)
- Faster Whisper (audio transcription)
- WebSockets

### Infrastructure
- Docker & Docker Compose
- Nginx (reverse proxy)
- Let's Encrypt / Certbot (SSL)
- PostgreSQL 16

---
