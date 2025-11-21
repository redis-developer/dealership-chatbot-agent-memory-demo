# Docker Setup for AutoEmporium Chatbot

This project uses Docker Compose to run both the frontend and backend together.

## Prerequisites

- Docker and Docker Compose installed
- Environment variables set (see `.env.example`)

## Quick Start

1. **Create a `.env` file** with your environment variables:
   ```bash
   OPENAI_API_KEY=your-openai-api-key
   MEMORY_SERVER_URL=http://host.docker.internal:8000
   ```

2. **Build and start all services:**
   ```bash
   docker-compose up --build
   ```

3. **Access the application:**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8001
   - API Health Check: http://localhost:8001/

## Services

### Backend (`backend`)
- **Port:** 8001
- **Container:** `autoemporium-backend`
- **Logs:** Available in `chatbot.log` file (mounted as volume)

### Frontend (`frontend`)
- **Port:** 3000 (mapped to nginx port 80)
- **Container:** `autoemporium-frontend`
- **Built with:** Vite + React + TypeScript
- **Served by:** Nginx

## Useful Commands

### Start services
```bash
docker-compose up
```

### Start in detached mode (background)
```bash
docker-compose up -d
```

### View logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f frontend
```

### Stop services
```bash
docker-compose down
```

### Rebuild after code changes
```bash
docker-compose up --build
```

### View running containers
```bash
docker-compose ps
```

### Access backend logs file
```bash
tail -f chatbot.log
```

## Development vs Production

### Development
For development, you might want to run services separately:
- Frontend: `npm run dev` (runs on port 5173)
- Backend: `python main.py` (runs on port 8001)

### Production (Docker)
Use Docker Compose for production-like environment:
- Frontend: Built and served by Nginx on port 3000
- Backend: Runs in container on port 8001

## Troubleshooting

### Backend not connecting to memory server
Make sure the memory server is running and accessible. The backend uses `host.docker.internal:8000` to connect to services on the host machine.

### Frontend can't reach backend
The frontend is built with `VITE_API_URL=http://localhost:8001` which works when accessing from the host machine. If you need to change this, update the build arg in `docker-compose.yml`.

### Port conflicts
If ports 3000 or 8001 are already in use, modify the port mappings in `docker-compose.yml`:
```yaml
ports:
  - "3001:80"  # Change frontend port
  - "8002:8001"  # Change backend port
```

