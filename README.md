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

**Docker Access (Required for PostgreSQL)**:  
If using PostgreSQL, ensure Docker is installed and your user can run Docker commands without `sudo`. If you get permission errors, add your user to the `docker` group:  
```bash
sudo usermod -aG docker $USER
```  
Log out and log back in (or restart your terminal) for changes to take effect. This allows the setup script to start PostgreSQL containers automatically.

### Setup

#### SQLite (Default, No Docker Required)
```bash
# Install dependencies
uv sync

# Setup database (SQLite is default)
uv run python scripts/setup_database.py

# Or specify explicitly
uv run python scripts/setup_database.py --db-type sqlite
```

#### PostgreSQL (Requires Docker)
```bash
# Install dependencies
uv sync

# Setup database (PostgreSQL service will be started automatically)
uv run python scripts/setup_database.py --db-type postgresql
```

# Start the platform
uv run python run.py
```

Platform runs at http://localhost:8000

### Shutdown/Cleanup

To stop the platform and clean up resources:

```bash
# Stop the platform (Ctrl+C in the terminal running uv run python run.py)

# If using PostgreSQL: Stop Docker services
docker compose --profile postgres down

# Or stop all Docker services
docker compose down

# If using SQLite: Optional cleanup of database files
rm finbot.db finbot.db-*
```
