# Docker Setup Guide

## Quick Start

### Build the Docker Image
```bash
docker build -t trail-chat-web .
```

### Run with Docker Compose (Recommended)
```bash
docker-compose up
```

Access at: **http://localhost:3001**

### Run with Docker CLI
```bash
docker run -p 3001:3001 --env-file .env trail-chat-web
```

## Configuration

### Environment Variables
Create a `.env` file with:
```env
OPENAI_API_KEY=your_openai_api_key_here
OPEN_AI_MODEL=gpt-4
SQLITE_DB_NAME=chat_history.db
```

### Persisted Data
The docker-compose setup persists these directories:
- `./data` - Chat history database
- `./cache` - AI response cache
- `./config` - Personality configurations

## Managing the Container

**Start in background:**
```bash
docker-compose up -d
```

**View logs:**
```bash
docker-compose logs -f
```

**Stop:**
```bash
docker-compose down
```

**Rebuild after code changes:**
```bash
docker-compose up --build
```

## Troubleshooting

### Port 3001 already in use
```bash
# Use a different port
docker run -p 8080:3001 --env-file .env trail-chat-web
```

### Container name conflict
```bash
docker rm -f trail-chat-web
docker-compose up
```

### View container status
```bash
docker ps -a
```

### Access container shell
```bash
docker exec -it trail-chat-web sh
```

## Files

- **[Dockerfile](Dockerfile)** - Simple, optimized build
- **[docker-compose.yml](docker-compose.yml)** - Container orchestration
- **[requirements-web-only.txt](requirements-web-only.txt)** - Minimal Python dependencies
- **[.dockerignore](.dockerignore)** - Files excluded from build
