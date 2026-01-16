#!/bin/bash
set -e

# Log all output
exec > >(tee /var/log/user-data.log) 2>&1
echo "Starting user data script at $(date)"

# Update system
apt-get update -y
apt-get upgrade -y

# Install required packages
apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    git

# Install Docker with buildx plugin included
if ! command -v docker &> /dev/null; then
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
    apt-get update -y
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    systemctl enable docker
    systemctl start docker
    usermod -aG docker ubuntu
fi

# Create docker-compose alias for compatibility
if ! command -v docker-compose &> /dev/null && docker compose version &> /dev/null; then
    cat > /usr/local/bin/docker-compose <<'EOF'
#!/bin/bash
docker compose "$@"
EOF
    chmod +x /usr/local/bin/docker-compose
fi

# Create application directory
APP_DIR="/opt/${app_name}"
mkdir -p $APP_DIR
cd $APP_DIR

# Clone repository
git clone https://github.com/redis-developer/dealership-chatbot-agent-memory-demo.git .

# Get public IP
PUBLIC_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)

# Update docker-compose.yml to use public IP for frontend API URL
sed -i "s|VITE_API_URL=http://localhost:8001|VITE_API_URL=http://$PUBLIC_IP:8001|g" $APP_DIR/docker-compose.yml

# Create .env file
cat > $APP_DIR/.env <<EOF
OPENAI_API_KEY=${openai_api_key}
REDIS_URL=${redis_url}
MEMORY_SERVER_URL=http://172.17.0.1:8000
CORS_ORIGINS=http://$PUBLIC_IP:3000,http://localhost:3000
EOF

# Set permissions
chown -R ubuntu:ubuntu $APP_DIR

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
cd $APP_DIR
docker compose down || true
docker compose build --no-cache
docker compose up -d

# Create systemd service for auto-start on reboot
cat > /etc/systemd/system/${app_name}.service <<'SERVICE_EOF'
[Unit]
Description=Dealership Chatbot Application
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/${app_name}
ExecStart=/bin/bash -c 'cd /opt/${app_name} && docker compose up -d'
ExecStop=/bin/bash -c 'cd /opt/${app_name} && docker compose down'
User=root

[Install]
WantedBy=multi-user.target
SERVICE_EOF

systemctl daemon-reload
systemctl enable ${app_name}.service

echo "Deployment completed at $(date)"
echo "Public IP: $PUBLIC_IP"
echo "Frontend: http://$PUBLIC_IP:3000"
echo "Backend: http://$PUBLIC_IP:8001"
echo "Memory Server: http://$PUBLIC_IP:8000"
