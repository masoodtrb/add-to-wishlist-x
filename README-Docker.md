# Docker Setup for Add Wishlist Project

This document explains how to run the Add Wishlist project using Docker and Docker Compose.

## Prerequisites

- Docker
- Docker Compose
- Make (optional, for using Makefile commands)

## Environment Setup

### 1. Environment Variables

Copy the appropriate environment file and configure it:

```bash
# For development
cp env.dev .env

# For production
cp env.prod .env
```

Edit the `.env` file with your actual values:

```bash
# Required variables
X_BEARER_TOKEN=your_actual_bearer_token
X_LIST_ID=your_list_id

# For production, also set:
REDIS_PASSWORD=your_secure_password
```

## Development Environment

### Quick Start

```bash
# Start all services
make dev

# Or manually:
docker-compose up -d
```

### Services

- **API**: http://localhost:8000
- **Flower (Celery monitoring)**: http://localhost:5555
- **Redis**: localhost:6379

### Development Features

- Hot reload enabled for code changes
- Source code mounted as volume
- Debug logging enabled
- All services connected via Docker network

### Useful Commands

```bash
# View logs
make logs

# Open shell in API container
make shell

# Stop services
make stop

# Restart services
make restart

# Health check
make health
```

## Production Environment

### Quick Start

```bash
# Start production services
make prod

# Or manually:
docker-compose -f docker-compose.prod.yml up -d
```

### Production Features

- Optimized for performance
- Redis password protection
- Multiple worker processes
- Nginx reverse proxy (optional)
- Health checks and restart policies
- Persistent volumes for data

### Production Services

- **API**: http://localhost:8000 (or through Nginx on port 80)
- **Flower**: http://localhost:5555 (optional)
- **Redis**: localhost:6379 (password protected)

### Production Commands

```bash
# View production logs
make logs-prod

# Open shell in production API container
make shell-prod

# Stop production services
docker-compose -f docker-compose.prod.yml down

# Restart production services
make restart-prod
```

## Docker Services

### API Service

- FastAPI application
- Uvicorn server
- Health check endpoint
- CORS enabled

### Redis Service

- Data persistence with AOF
- Health checks
- Password protection (production)

### Celery Worker

- Background task processing
- Rate limiting compliance
- Auto-restart on failure

### Celery Beat

- Scheduled tasks
- Persistent schedule storage
- Auto-restart on failure

### Flower (Optional)

- Celery task monitoring
- Web-based dashboard
- Real-time task status

### Nginx (Production)

- Reverse proxy
- Rate limiting
- Security headers
- SSL termination (configurable)

## Configuration

### Environment Variables

| Variable         | Description        | Default             |
| ---------------- | ------------------ | ------------------- |
| `X_BEARER_TOKEN` | X API Bearer Token | Required            |
| `X_LIST_ID`      | X List ID          | 1979623501649567798 |
| `REDIS_HOST`     | Redis hostname     | redis               |
| `REDIS_PORT`     | Redis port         | 6379                |
| `REDIS_DB`       | Redis database     | 0                   |
| `REDIS_PASSWORD` | Redis password     | (empty for dev)     |
| `API_HOST`       | API bind address   | 0.0.0.0             |
| `API_PORT`       | API port           | 8000                |

### Volume Mounts

- **Development**: Source code mounted for hot reload
- **Production**: Persistent volumes for Redis data and Celery beat schedule

### Network Configuration

- All services communicate via Docker network
- Internal service discovery
- Isolated from host network

## Monitoring and Logs

### Health Checks

```bash
# Check API health
curl http://localhost:8000/health

# Check all services
docker-compose ps
```

### Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f api
docker-compose logs -f celery-worker
docker-compose logs -f redis
```

### Flower Dashboard

Access the Celery monitoring dashboard at http://localhost:5555 to:

- Monitor task execution
- View task history
- Check worker status
- Inspect task details

## Troubleshooting

### Common Issues

1. **Port conflicts**: Ensure ports 8000, 5555, and 6379 are available
2. **Environment variables**: Check that `.env` file is properly configured
3. **Redis connection**: Verify Redis service is healthy
4. **X API token**: Ensure valid Bearer token is set

### Debug Commands

```bash
# Check container status
docker-compose ps

# Check logs for errors
docker-compose logs --tail=50

# Inspect container
docker-compose exec api bash

# Check Redis connection
docker-compose exec redis redis-cli ping
```

### Cleanup

```bash
# Stop and remove all containers
make clean

# Remove specific volumes
docker volume rm add-whishlist_redis_data
docker volume rm add-whishlist_celery_beat_data
```

## Security Considerations

### Development

- Redis without password (local development only)
- CORS enabled for all origins
- Debug logging enabled

### Production

- Redis password protection
- Restricted CORS (configure as needed)
- Nginx rate limiting
- Security headers
- SSL/TLS termination (configure certificates)

## Scaling

### Horizontal Scaling

```bash
# Scale Celery workers
docker-compose up -d --scale celery-worker=3

# Scale API instances (with load balancer)
docker-compose up -d --scale api=3
```

### Resource Limits

Add resource limits to docker-compose files:

```yaml
services:
  api:
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: "0.5"
```

## Backup and Recovery

### Redis Data Backup

```bash
# Create backup
docker-compose exec redis redis-cli BGSAVE

# Copy backup file
docker cp add-wishlist-redis:/data/dump.rdb ./backup/
```

### Volume Backup

```bash
# Backup volumes
docker run --rm -v add-wishlist_redis_data:/data -v $(pwd):/backup alpine tar czf /backup/redis_backup.tar.gz -C /data .
```
