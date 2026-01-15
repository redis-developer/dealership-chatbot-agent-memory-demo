# AWS Configuration
variable "aws_region" {
  description = "AWS region for deployment"
  type        = string
  default     = "us-east-1"
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t3.medium"
}

variable "key_name" {
  description = "Name of the SSH key pair in AWS"
  type        = string
}

# Application Configuration
variable "app_name" {
  description = "Application name for resource naming"
  type        = string
  default     = "dealership-chatbot"
}

variable "environment" {
  description = "Environment (dev, staging, prod)"
  type        = string
  default     = "dev"
}

# Redis Configuration
variable "redis_url" {
  description = "Redis Cloud connection URL"
  type        = string
  sensitive   = true
}

# OpenAI Configuration
variable "openai_api_key" {
  description = "OpenAI API key"
  type        = string
  sensitive   = true
}

# Memory Server Configuration
variable "memory_server_url" {
  description = "Agent Memory Server URL (use http://localhost:8000 if running locally on EC2)"
  type        = string
  default     = "http://localhost:8000"
}

# Network Configuration
variable "allowed_ssh_cidr" {
  description = "CIDR block allowed for SSH access"
  type        = string
  default     = "0.0.0.0/0"
}

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "public_subnet_cidr" {
  description = "CIDR block for public subnet"
  type        = string
  default     = "10.0.1.0/24"
}

