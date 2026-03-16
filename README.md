# OWASP FinBot CTF

See Collaborator Hub for details on this project: https://github.com/OWASP-ASI/FinBot-CTF-workstream


## Dev Guide (Temporary)

** Warning: `main` branch is potentially unstable **

### Prerequisites

Check if you have the required tools installed:
```bash
python scripts/check_prerequisites.py
```

**Required:**
- Python 3.13+
- [uv](https://docs.astral.sh/uv/) package manager

**Optional (for full development environment):**
- Docker Desktop (for PostgreSQL, Redis, MailHog, etc.)

### Quick Start

#### Option 1: SQLite (Simplest - No Docker Required)

```bash
# Install dependencies
uv sync

# Setup SQLite database
uv run python scripts/setup_database.py

# Start the platform
uv run python run.py
```

Platform runs at http://localhost:8000

#### Option 2: Full Development Stack (Docker)

```bash
# Install dependencies
uv sync

# Start all development services
docker compose up -d

# Setup PostgreSQL database
uv run python scripts/setup_database.py --db-type postgresql

# Start the platform
uv run python run.py
```

**Access Points:**
- **Application**: http://localhost:8000
- **MailHog UI**: http://localhost:8025 (email testing)
- **PostgreSQL**: `localhost:5432`
- **Redis**: `localhost:6379`

### Development Services

The `docker-compose.yml` provides a complete development environment:

| Service | Port(s) | Purpose | Required? |
|---------|---------|---------|-----------|
| **PostgreSQL** | 5432 | Production-like database | Optional (use for testing PostgreSQL features) |
| **Redis** | 6379 | Cache & message queue | Optional (required for multi-agent features) |
| **MailHog** | 1025 (SMTP)<br/>8025 (UI) | Email testing - captures all outbound emails | Optional (for testing email features) |
| **Google Drive Emulator** | 4443 | Mock Google Drive API | Optional (for testing Drive integrations) |

**Starting specific services:**
```bash
# Just database
docker compose up -d postgres

# Database + email testing
docker compose up -d postgres mailhog

# Everything
docker compose up -d
```

**Stopping services:**
```bash
docker compose down
```

**Viewing logs:**
```bash
docker compose logs -f [service-name]
```

For detailed service documentation, see [docs/development-services.md](docs/development-services.md).

### Configuration

**Environment Variables:**
- Copy `config/dev-services.env` to `.env` for Docker service integration
- See `finbot/config.py` for all available settings
- Use `--db-type` flag to override database type: `--db-type postgresql` or `--db-type sqlite`

**Database Selection:**
- **SQLite** (default): Best for local development, no Docker needed
- **PostgreSQL**: Use when testing production behavior or multi-user scenarios

### Common Commands

```bash
# Check prerequisites
python scripts/check_prerequisites.py

# Setup/reset database
uv run python scripts/setup_database.py [--db-type sqlite|postgresql]

# Start application
uv run python run.py

# Run tests
uv run pytest

# View email in development
open http://localhost:8025
```
