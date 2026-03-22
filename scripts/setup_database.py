"""
Setup the database for the FinBot platform
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

# Parse args BEFORE importing settings so we can set env vars
parser = argparse.ArgumentParser(description="Setup the FinBot database")
parser.add_argument(
    "--db-type",
    choices=["sqlite", "postgresql"],
    help="Database type to use (overrides DATABASE_TYPE env var)",
)
parser.add_argument(
    "--install-method",
    choices=["docker", "local"],
    default="docker",
    help="Installation method for PostgreSQL (docker or local). Default: docker",
)
args = parser.parse_args()

# Set environment variable BEFORE importing settings
if args.db_type:
    os.environ["DATABASE_TYPE"] = args.db_type

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# pylint: disable=wrong-import-position
# ruff: noqa: E402
from finbot.config import settings

# Import models to register them with the declarative base
from finbot.core.data import models  # noqa: F401
from finbot.core.data.database import (
    create_tables,
    get_database_info,
    test_database_connection,
)


def setup_postgresql() -> bool:
    """Setup the PostgreSQL database"""
    if args.install_method == "local":
        return setup_postgresql_local()
    else:
        return setup_postgresql_docker()


def setup_postgresql_docker() -> bool:
    """Setup PostgreSQL using Docker"""
    print("Setting up PostgreSQL database via Docker...")

    # Start PostgreSQL service if not running
    print("Ensuring PostgreSQL service is running...")
    try:
        result = subprocess.run(
            ["docker", "compose", "--profile", "postgres", "up", "-d", "postgres"],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=True
        )
        if "done" in result.stdout.lower() or "started" in result.stdout.lower():
            print("✅ PostgreSQL service started")
        else:
            print("ℹ️  PostgreSQL service already running")
    except subprocess.CalledProcessError as e:
        print(f"⚠️  Could not start PostgreSQL service: {e.stderr}")
        print("Assuming it's already running...")

    try:
        # pylint: disable=import-outside-toplevel
        import psycopg2
        from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

        # connect to PostgreSQL
        conn = psycopg2.connect(
            host=settings.POSTGRES_HOST,
            port=settings.POSTGRES_PORT,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD,
            database="postgres",  # connect to default to figure things out.
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)

        cursor = conn.cursor()

        # create db if it doesn't exist
        cursor.execute(
            f"SELECT 1 FROM pg_catalog.pg_database WHERE datname = '{settings.POSTGRES_DB}'"
        )
        exists = cursor.fetchone()
        if not exists:
            cursor.execute(f"CREATE DATABASE {settings.POSTGRES_DB}")
            print(f"Database {settings.POSTGRES_DB} created successfully")
        else:
            print(f"Database {settings.POSTGRES_DB} already exists")

        cursor.close()
        conn.close()
        return True
    except ImportError:
        print("❌ psycopg2 is not installed")
        print("   Install: uv sync")
        return False
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"❌ Error setting up PostgreSQL database: {e}")
        print("\n💡 Quick fix:")
        print("   1. Start PostgreSQL: docker compose up -d postgres")
        print("   2. Wait a few seconds for it to start")
        print("   3. Re-run this script")
        return False


def setup_postgresql_local() -> bool:
    """Setup PostgreSQL using local installation"""
    import platform

    print("Setting up PostgreSQL database via local installation...")

    os_name = platform.system().lower()
    print(f"Detected OS: {os_name}")

    if os_name == "linux":
        print("Assuming Ubuntu/Debian-based Linux...")
        print("To install PostgreSQL locally, run the following commands:")
        print("sudo apt update")
        print("sudo apt install postgresql postgresql-contrib")
        print("sudo systemctl start postgresql")
        print("sudo systemctl enable postgresql")
        print("sudo -u postgres createuser --createdb --superuser $USER")
        print("createdb finbot")
        print("After installing and starting PostgreSQL, re-run this script.")
    elif os_name == "darwin":  # macOS
        print("Assuming macOS...")
        print("To install PostgreSQL locally, install via Homebrew:")
        print("brew install postgresql")
        print("brew services start postgresql")
        print("createdb finbot")
        print("After installing and starting PostgreSQL, re-run this script.")
    elif os_name == "windows":
        print("Assuming Windows...")
        print("To install PostgreSQL locally:")
        print("1. Download and install from: https://www.postgresql.org/download/windows/")
        print("2. During installation, set password for 'postgres' user")
        print("3. Add PostgreSQL bin directory to PATH")
        print("4. Open command prompt as Administrator and run:")
        print('   createuser --createdb --superuser "%USERNAME%"')
        print("   createdb finbot")
        print("After installing and starting PostgreSQL, re-run this script.")
    else:
        print(f"Unsupported OS: {os_name}")
        print("Please install PostgreSQL manually and ensure it's running.")
        print("Then re-run this script.")

    return False  # Indicate manual setup needed


def setup_sqlite() -> bool:
    """Setup the SQLite database"""

    print("📁 Setting up SQLite database...")

    try:
        db_path = settings.get_database_url().replace("sqlite:///", "")
        db_dir = os.path.dirname(db_path)

        # Create directory if needed
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            print(f"📁 Created directory: {db_dir}")

        print(f"📄 SQLite database will be created at: {db_path}")
        return True

    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"❌ SQLite setup failed: {e}")
        return False


def main() -> None:
    """DB Setup Script"""
    print("🚀 FinBot CTF Database Setup")
    print(f"Database Type: {settings.DATABASE_TYPE}")
    print(f"Database URL: {settings.get_database_url()}")
    print()

    # DB specific setup
    if settings.DATABASE_TYPE == "sqlite":
        if not setup_sqlite():
            sys.exit(1)
    elif settings.DATABASE_TYPE == "postgresql":
        if not setup_postgresql():
            sys.exit(1)
    else:
        print(f"Unsupported database type: {settings.DATABASE_TYPE}")
        sys.exit(1)

    # Test Connection
    print("Testing database connection...")
    if not test_database_connection():
        sys.exit(1)

    # Create Tables
    print("Creating database tables...")
    try:
        create_tables()
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"❌ Error creating database tables: {e}")
        sys.exit(1)

    # Verification
    print("Verifying database setup...")
    db_info = get_database_info()

    print("✅ Database setup complete")
    print(f"Database: {db_info['type']} ({db_info.get('version', 'Unknown version')})")
    print(f"Tables created: {len(db_info['tables'])}")
    print(f"Tables: {', '.join(db_info['tables'])}")


if __name__ == "__main__":
    main()
