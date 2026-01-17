# Car Dealership Agent with Redis Agent Memory Server

<p>
  <a href="https://github.com/redis/agent-memory-server"><img src="https://img.shields.io/badge/Redis-Agent%20Memory%20Server-red?logo=redis" alt="Redis Agent Memory Server"></a>
  <a href="https://python.langchain.com/"><img src="https://img.shields.io/badge/LangChain-Powered-blue" alt="LangChain"></a>
  <a href="https://langchain-ai.github.io/langgraph/"><img src="https://img.shields.io/badge/LangGraph-Workflow-green" alt="LangGraph"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"></a>
</p>

Car dealership AI agent that demonstrates how Redis Agent Memory Server enables long-term memory and conversation context retrieval, allowing the agent to remember customer preferences across sessions and provide personalized car purchase assistance.

## Table of Contents

- [Demo Objectives](#demo-objectives)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Getting Started](#getting-started)
  - [1. Clone the Repository](#1-clone-the-repository)
  - [2. Environment Configuration](#2-environment-configuration)
  - [3. Start Agent Memory Server](#3-start-agent-memory-server)
  - [4. Run with Docker](#4-run-with-docker)
  - [5. Run for Development](#5-run-for-development)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Usage](#usage)
- [Docker Commands Reference](#docker-commands-reference)
- [Cloud Deployment](#cloud-deployment)
- [Resources](#resources)
- [Maintainers](#maintainers)
- [License](#license)

## Demo Objectives

- **Long-term memory storage** using Redis Agent Memory Server for persistent customer preferences
- **Short-term/working memory** using LangGraph checkpointers and Redis Agent Memory Server
- **Conversation context retrieval** for personalized interactions across sessions
- **Agentic orchestration** with LangGraph workflow stages (needs analysis → shortlist → test drive → financing)

## Tech Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Memory** | [Redis Agent Memory Server](https://github.com/redis/agent-memory-server) | Long-term and working memory management |
| **Database** | [Redis Cloud](https://redis.io/cloud/) | Vector storage and session persistence |
| **Orchestration** | [LangGraph](https://langchain-ai.github.io/langgraph/) | Stateful workflow management |
| **LLM Framework** | [LangChain](https://python.langchain.com/) | LLM integration and prompting |
| **Backend** | [FastAPI](https://fastapi.tiangolo.com/) | Python REST API |
| **Frontend** | [React 18](https://react.dev/) + TypeScript | User interface |
| **Styling** | [Tailwind CSS](https://tailwindcss.com/) | UI styling |
| **LLM** | [OpenAI GPT-4](https://openai.com/) | Language model |
| **Deployment** | Docker + Terraform | Containerization and cloud infrastructure |

## Prerequisites

- Python 3.11+
- Node.js 18+
- Docker and Docker Compose
- Redis Cloud account or local Redis instance
- OpenAI API key

## Getting Started

### 1. Clone the Repository

```bash
git clone <repository-url>
cd dealership-chatbot-agent-memory-demo
```

### 2. Environment Configuration

Create a `.env` file in the project root:

```bash
OPENAI_API_KEY=your_openai_api_key_here
REDIS_URL=redis://default:password@your-redis-host:port
MEMORY_SERVER_URL=http://localhost:8000
```

### 3. Start Agent Memory Server

Get the pre-built Docker image from [Docker Hub](https://hub.docker.com/r/redislabs/agent-memory-server):

```bash
docker run -p 8000:8000 \
  -e REDIS_URL=redis://default:<password>@<your-redis-host>:<port> \
  -e OPENAI_API_KEY=<your-openai-api-key> \
  redislabs/agent-memory-server:latest \
  agent-memory api --host 0.0.0.0 --port 8000 --task-backend=asyncio
```

> **Note:** This command starts the Agent Memory Server API with asyncio task backend. You must have a running Redis instance (e.g., Redis Cloud) accessible at the URL you provide.

### 4. Run with Docker

Build and start all services:

```bash
docker-compose up --build
```

Access the application:
- **Frontend:** http://localhost:3000
- **Backend API:** http://localhost:8001

### 5. Run for Development

**Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

## Screenshots

![Landing Page](images/landing_page.png)
![Chatbot Interface](images/chat_window.png)

## Architecture

![Architecture_diagram](images/Screenshot.png)

### Architecture Flow

```
User Query
    ↓
[Retrieve Conversation Context] → Load past preferences from long-term memory
    ↓
[Parse Slots] → Extract car preferences using LLM
    ↓
[Ensure Readiness] → Check if all required slots are filled
    ↓
[Decide Next]
    ├→ Missing slots? → Ask follow-up question
    └→ All slots filled? → Advance to next stage
         ↓
    [Workflow Stages]
         ├→ Brand Selected? → Suggest Models
         ├→ Model Selected? → Suggest Test Drive
         ├→ Test Drive Completed? → Suggest Financing
         └→ Financing Discussed? → Prepare for Delivery
         ↓
    [Save to Memory] → Store conversation and preferences
         ↓
    Response to User
```

## Project Structure

```
dealership-chatbot-agent-memory-demo/
├── backend/
│   ├── main.py              # FastAPI application
│   ├── orchestrator.py      # LangGraph workflow
│   └── requirements.txt     # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── components/      # React components
│   │   └── contexts/        # React contexts
│   ├── package.json
│   └── nginx.conf           # Production server config
├── docker/
│   ├── Dockerfile.backend
│   └── Dockerfile.frontend
├── terraform/
│   ├── main.tf               # AWS infrastructure
│   ├── variables.tf          # Variable definitions
│   ├── outputs.tf            # Output definitions
│   └── user_data.sh          # EC2 bootstrap script
├── docker-compose.yml
└── README.md
```

## Usage

1. **Start a conversation** by logging in with any username
2. **Share your preferences** (e.g., "I'm looking for a 5-seater SUV")
3. **Browse recommendations** based on your requirements
4. **Select a model** and schedule a test drive
5. **Complete the journey** through financing options

The agent remembers your preferences across sessions, so returning customers get personalized recommendations immediately.


## Cloud Deployment

Deploy to AWS EC2 using Terraform.

**Prerequisites:**
- AWS account with credentials configured
- Terraform installed (>= 1.0)
- SSH key pair in AWS EC2

**Quick Start:**

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your values
terraform init
terraform plan
terraform apply
```

**Full deployment guide:** See [terraform/README.md](terraform/README.md) for detailed instructions.

## Resources

- [Redis Agent Memory Server](https://github.com/redis/agent-memory-server)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [LangChain Documentation](https://python.langchain.com/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Redis Cloud](https://redis.io/cloud/)

## Maintainers

- **Bhavana Giri** — [@bhavanagiri](https://github.com/bhavanagiri)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
