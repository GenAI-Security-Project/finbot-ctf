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

You'll also need Node.js and npm for building CSS:
```bash
node --version  # v18 or higher recommended
npm --version   # v9 or higher recommended
```

### Setup

```bash
# Install Python dependencies
uv sync

# Install Node dependencies for CSS build
npm install

# Build Tailwind CSS (required for styling)
npm run build:css

# Setup database (defaults to sqlite)
uv run python scripts/setup_database.py

# Or specify database type explicitly
uv run python scripts/setup_database.py --db-type sqlite

# For PostgreSQL: start the database server first
docker compose up -d postgres
uv run python scripts/setup_database.py --db-type postgresql

# Start the platform
uv run python run.py
```

Platform runs at http://localhost:8000

### Development Workflow

**CSS Development**: When modifying Tailwind classes in templates, rebuild CSS:

```bash
# One-time build (production)
npm run build:css

# Watch mode (rebuilds automatically on template changes)
npm run watch:css

# Development build (unminified, faster)
npm run dev:css
```

**Customizing Styles**: Edit `tailwind.config.js` to customize theme colors, fonts, animations, etc. All custom colors from the various portals (admin, vendor, CTF) are already configured.
