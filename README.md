# OWASP FinBot CTF

See Collaborator Hub for details on this project: https://github.com/OWASP-ASI/FinBot-CTF-workstream


## Dev Guide (Temporary)

** Warning: `main` branch is potentially unstable **

Please follow below instructions to test drive the current branch

### Prerequisites

Check if you have the required tools:
```bash
python scripts/check_prerequisites.py
```

### Environment Setup

Create and activate a virtual environment (optional but recommended):
```bash
# Create virtual environment
uv venv

# Activate on macOS/Linux
source .venv/bin/activate

# Activate on Windows
.venv\Scripts\activate
```

Install dependencies:
```bash
uv sync
```

Set up database (defaults to sqlite):
```bash
uv run python scripts/setup_database.py

# Or specify database type explicitly
uv run python scripts/setup_database.py --db-type sqlite
```

For PostgreSQL, start the database server first:
```bash
docker compose up -d postgres
```
```bash
uv run python scripts/setup_database.py --db-type postgresql
```

Start the platform:
```bash
uv run python run.py
```

Platform runs at http://localhost:8000
