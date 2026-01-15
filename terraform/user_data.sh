#!/bin/bash
set -e

# Log all output
exec > >(tee /var/log/user-data.log) 2>&1
echo "Starting user data script at $(date)"

# Update system
dnf update -y

# Install Docker
dnf install -y docker git
systemctl start docker
systemctl enable docker

# Install Docker Compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Add ec2-user to docker group
usermod -aG docker ec2-user

# Create application directory
mkdir -p /opt/${app_name}
cd /opt/${app_name}

# Clone the repository
git clone https://github.com/redis-developer/dealership-chatbot-agent-memory-demo.git .

# Create .env file
cat > .env << 'EOF'
OPENAI_API_KEY=${openai_api_key}
REDIS_URL=${redis_url}
MEMORY_SERVER_URL=${memory_server_url}
EOF

# Set permissions
chown -R ec2-user:ec2-user /opt/${app_name}

# Start Agent Memory Server
docker run -d \
  --name agent-memory-server \
  --restart unless-stopped \
  -p 8000:8000 \
  -e REDIS_URL="${redis_url}" \
  -e OPENAI_API_KEY="${openai_api_key}" \
  redislabs/agent-memory-server:latest \
  agent-memory api --host 0.0.0.0 --port 8000 --task-backend=asyncio

# Wait for memory server to be ready
echo "Waiting for Agent Memory Server to start..."
sleep 10

# Build and start application services
cd /opt/${app_name}
docker-compose up -d --build

echo "Deployment completed at $(date)"
echo "Frontend: http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4):3000"
echo "Backend: http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4):8001"
echo "Memory Server: http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4):8000"

