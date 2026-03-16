# Development Services

This document describes the development services available via Docker Compose.

## Services Overview

### PostgreSQL (Port 5432)
- **Purpose**: Primary database for persistent storage
- **Access**: `postgresql://postgres:postgres@localhost:5432/finbot`
- **Admin**: Use tools like pgAdmin or DBeaver

### Redis (Port 6379)
- **Purpose**: Cache, message queue, and session storage
- **Access**: `redis://localhost:6379`
- **CLI**: `docker compose exec redis redis-cli`

### MailHog (Ports 1025, 8025)
- **Purpose**: Email testing - captures all outbound emails
- **SMTP**: `localhost:1025` (configure your app to send here)
- **Web UI**: http://localhost:8025
- **Features**:
  - View all sent emails in browser
  - Test email templates
  - No emails actually sent to real addresses
  - JSON/HTML API for testing

### Google Drive Emulator (Port 4443)
- **Purpose**: Mock Google Drive API for testing
- **API Endpoint**: http://localhost:4443
- **Note**: Uses fake-gcs-server as base. For full Drive API compatibility, consider:
  - Custom mock server with Drive v3 API
  - Test with actual service account in isolated workspace
  - Use VCR.py for recording/replaying API calls

## Starting Services

### Start all services:
```bash
docker compose up -d
```

### Start specific services:
```bash
docker compose up -d postgres redis
docker compose up -d mailhog
docker compose up -d google-drive-emulator
```

## Accessing Services

### MailHog Web Interface
Open browser: http://localhost:8025

### Configure Application to Use MailHog
```python
# finbot/config.py
SMTP_HOST = "localhost"
SMTP_PORT = 1025
SMTP_USER = ""  # Not required for MailHog
SMTP_PASSWORD = ""
```

### Test Email Sending
```python
import smtplib
from email.message import EmailMessage

msg = EmailMessage()
msg['Subject'] = 'Test Email'
msg['From'] = 'noreply@finbot.local'
msg['To'] = 'user@example.com'
msg.set_content('This is a test email!')

with smtplib.SMTP('localhost', 1025) as smtp:
    smtp.send_message(msg)
```

Then check http://localhost:8025 to see the captured email.

## Stopping Services

```bash
docker compose down
```

## Cleaning Up (removes data)

```bash
docker compose down -v
```

## Health Checks

Check service health:
```bash
docker compose ps
```

View logs:
```bash
docker compose logs -f mailhog
docker compose logs -f postgres
```

## Environment Variables

Copy the example config:
```bash
cp config/dev-services.env .env
```

Load in your application to use these services.
