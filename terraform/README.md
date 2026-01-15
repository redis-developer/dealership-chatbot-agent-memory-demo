# Terraform Deployment for Dealership Chatbot

Deploy the Car Dealership Agent to AWS EC2 using Terraform.

## Prerequisites

- AWS account with CLI configured (`aws configure`)
- Terraform installed (>= 1.0)
- SSH key pair created in AWS EC2
- OpenAI API key
- Redis Cloud account with a database

## Quick Start

1. **Copy and configure variables:**

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
```

2. **Edit `terraform.tfvars` with your values:**

```hcl
aws_region     = "us-east-1"
key_name       = "your-key-pair-name"
redis_url      = "redis://default:password@your-redis-host:port"
openai_api_key = "sk-your-openai-api-key"
```

3. **Initialize and deploy:**

```bash
terraform init
terraform plan
terraform apply
```

4. **Access the application:**

After deployment completes, Terraform outputs the URLs:

```
frontend_url      = "http://<public-ip>:3000"
backend_url       = "http://<public-ip>:8001"
memory_server_url = "http://<public-ip>:8000"
ssh_command       = "ssh -i <your-key.pem> ec2-user@<public-ip>"
```

## Configuration Options

| Variable | Description | Default |
|----------|-------------|---------|
| `aws_region` | AWS region for deployment | `us-east-1` |
| `instance_type` | EC2 instance type | `t3.medium` |
| `key_name` | SSH key pair name | Required |
| `redis_url` | Redis Cloud connection URL | Required |
| `openai_api_key` | OpenAI API key | Required |
| `memory_server_url` | Agent Memory Server URL | `http://localhost:8000` |
| `allowed_ssh_cidr` | CIDR for SSH access | `0.0.0.0/0` |

## Architecture

The deployment creates:

- **VPC** with public subnet and internet gateway
- **EC2 instance** (Amazon Linux 2023) with Docker
- **Security group** allowing ports 22, 80, 443, 3000, 8000, 8001
- **Elastic IP** for stable public access

Services running on EC2:

- **Agent Memory Server** (port 8000) - Redis-backed memory management
- **Backend API** (port 8001) - FastAPI application
- **Frontend** (port 3000) - React application via nginx

## SSH Access

```bash
ssh -i your-key.pem ec2-user@<public-ip>
```

## View Logs

```bash
# SSH into instance, then:

# View startup logs
cat /var/log/user-data.log

# View Docker containers
docker ps

# View application logs
cd /opt/dealership-chatbot
docker-compose logs -f
```

## Update Application

```bash
# SSH into instance
ssh -i your-key.pem ec2-user@<public-ip>

# Pull latest code and restart
cd /opt/dealership-chatbot
git pull
docker-compose down
docker-compose up -d --build
```

## Destroy Infrastructure

```bash
terraform destroy
```

## Troubleshooting

### Services not starting

Check the user data log:
```bash
cat /var/log/user-data.log
```

### Memory server not connecting

Ensure Redis Cloud URL is correct and the database is accessible:
```bash
docker logs agent-memory-server
```

### Frontend can't reach backend

The frontend is configured to connect to `localhost:8001`. If accessing remotely, ensure the backend URL is correctly set in the environment.

