# Add Wishlist

A FastAPI application for managing X (Twitter) lists with queue-based processing to comply with free plan rate limits.

## Features

- FastAPI REST API
- Celery background task processing
- Redis for data storage and message queuing
- Rate limiting compliance (15-minute intervals)
- Docker support for development and production

## Quick Start

### Development

```bash
# Copy environment file
cp env.dev .env
# Edit .env with your X API token

# Start with Docker Compose
docker-compose up -d
```

### Production

```bash
# Copy environment file
cp env.prod .env
# Edit .env with your production settings

# Start production environment
docker-compose -f docker-compose.prod.yml up -d
```

## API Endpoints

- `GET /health` - Health check
- `POST /queue-user` - Queue user for processing
- `GET /queue-status` - Check queue status
- `GET /all-tasks-status` - Get comprehensive status
- `POST /add-user` - Store username in Redis
- `GET /get-users` - Retrieve stored usernames

## Services

- **API**: http://localhost:8000
- **Flower**: http://localhost:5555 (Celery monitoring)
- **Redis**: localhost:6379

For detailed Docker setup instructions, see [README-Docker.md](README-Docker.md).
