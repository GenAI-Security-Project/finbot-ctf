# OWASP FinBot CTF

AI-powered invoice fraud detection platform using **free, local LLMs** (Ollama). No API keys or costs required.

See Collaborator Hub for details on this project: https://github.com/OWASP-ASI/FinBot-CTF-workstream


## Dev Guide (Temporary)

** Warning: `main` branch is potentially unstable **

Please follow below instructions to test drive the current branch

### Prerequisites

Check if you have the required tools:
```bash
python scripts/check_prerequisites.py
```

### Setup

```bash
# Install dependencies
uv sync

# Start all required services: PostgreSQL, Redis, and Ollama
docker compose up -d

# Pull an LLM model into the Ollama container (first time only)
docker exec -it finbot-ollama ollama pull llama3.2

# Setup database
uv run python scripts/setup_database.py --db-type postgresql

# Start the platform
uv run python run.py
```

Platform runs at http://localhost:8000



### Notes on LLM Setup (Ollama - Free & Local)

This project uses **Ollama** for AI-powered fraud detection - completely free and runs locally via Docker:

The `docker compose up -d` command automatically starts Ollama. To pull additional models, e.g. if you don't have a lot of memory or disk space where you are testing:

```bash
# Pull a model (first time setup)
docker exec -it finbot-ollama ollama pull llama3.2

# List available models
docker exec -it finbot-ollama ollama list

# Try other models:
# Smaller, faster model (recommended for testing)
docker exec -it finbot-ollama ollama pull llama3.2

# Larger, more capable model
docker exec -it finbot-ollama ollama pull llama3.1

# Very small, fast model
docker exec -it finbot-ollama ollama pull qwen2.5:0.5b
```

**Note:** Ollama runs in Docker by default. If you prefer to run it natively on your machine instead, install from https://ollama.ai and change `OLLAMA_BASE_URL` in `.env`.

### Configuration

Create a `.env` file:

```bash
# Database
DATABASE_TYPE=postgresql

# LLM Provider (ollama or mock)
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
LLM_DEFAULT_MODEL=llama3.2

# For testing without Ollama, use:
# LLM_PROVIDER=mock
```