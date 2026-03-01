# Deployment Guide

## Overview

This guide covers deploying mr_bot to production environments. Follow these steps to ensure a secure, reliable deployment.

> 🚀 **Quick Deploy**: For testing, you can run locally. For production, follow this guide carefully.

---

## 📋 Pre-Deployment Checklist

### 1. Environment Preparation

```bash
# Clone the repository
git clone <repository-url>
cd mr_bot

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

```bash
# Copy example configuration
cp config.example.py config.py

# Edit configuration
nano config.py  # or your preferred editor
```

**Required Environment Variables:**

```bash
# Flask (set to false for production)
export FLASK_DEBUG=false

# LLM Provider (choose one)
export OPENAI_API_KEY="sk-..."
# or
export ANTHROPIC_API_KEY="sk-ant-..."
# or use local Ollama (no key needed)

# MS Teams (if using)
export MSTEAMS_APP_ID="your-app-id"
export MSTEAMS_APP_PASSWORD="your-app-password"

# Telegram (if using)
export TELEGRAM_BOT_TOKEN="your-bot-token"
```

### 3. Security Validation

```bash
# Run Python to validate configuration
python -c "import config; print('Config validation:', config.validate_config())"
```

You should see no warnings about placeholder credentials.

---

## 🖥️ Deployment Options

### Option 1: Direct Server Deployment

#### Using Gunicorn (Recommended for Linux)

```bash
# Install gunicorn
pip install gunicorn

# Run with gunicorn (production WSGI server)
gunicorn -w 4 -b 0.0.0.0:3978 bot:app
```

**Options explained:**
- `-w 4`: 4 worker processes (adjust based on CPU cores)
- `-b 0.0.0.0:3978`: Bind to all interfaces on port 3978
- `bot:app`: Module `bot`, Flask app object `app`

#### Using Waitress (Windows/Linux)

```bash
# Install waitress
pip install waitress

# Run with waitress
waitress-serve --port=3978 bot:app
```

### Option 2: Docker Deployment

#### Dockerfile

```dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 botuser && chown -R botuser:botuser /app
USER botuser

# Create data directory
RUN mkdir -p data/sessions data/memory

# Expose port
EXPOSE 3978

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:3978/')" || exit 1

# Run with gunicorn
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:3978", "bot:app"]
```

#### Build and Run

```bash
# Build image
docker build -t mr_bot:latest .

# Run container
docker run -d \
  --name mr_bot \
  -p 3978:3978 \
  -e FLASK_DEBUG=false \
  -e OPENAI_API_KEY="$OPENAI_API_KEY" \
  -v $(pwd)/data:/app/data \
  mr_bot:latest
```

### Option 3: Docker Compose

#### docker-compose.yml

```yaml
version: '3.8'

services:
  mr_bot:
    build: .
    container_name: mr_bot
    restart: unless-stopped
    ports:
      - "3978:3978"
    environment:
      - FLASK_DEBUG=false
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - MSTEAMS_APP_ID=${MSTEAMS_APP_ID}
      - MSTEAMS_APP_PASSWORD=${MSTEAMS_APP_PASSWORD}
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    healthcheck:
      test: ["CMD", "python", "-c", "import requests; requests.get('http://localhost:3978/')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

Run with:
```bash
docker-compose up -d
```

---

## 🌐 Reverse Proxy Setup

### Nginx Configuration

```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    # SSL certificates
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    
    # Proxy to Flask app
    location / {
        proxy_pass http://127.0.0.1:3978;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }
}
```

### Apache Configuration

```apache
<VirtualHost *:80>
    ServerName your-domain.com
    Redirect permanent / https://your-domain.com/
</VirtualHost>

<VirtualHost *:443>
    ServerName your-domain.com
    
    SSLEngine on
    SSLCertificateFile /path/to/cert.pem
    SSLCertificateKeyFile /path/to/key.pem
    
    ProxyPreserveHost On
    ProxyPass / http://127.0.0.1:3978/
    ProxyPassReverse / http://127.0.0.1:3978/
    
    # Security headers
    Header always set X-Frame-Options "SAMEORIGIN"
    Header always set X-Content-Type-Options "nosniff"
    Header always set X-XSS-Protection "1; mode=block"
</VirtualHost>
```

---

## ☁️ Cloud Deployment

### AWS Elastic Beanstalk

1. Create `ebextensions/python.config`:
```yaml
option_settings:
  aws:elasticbeanstalk:container:python:
    WSGIPath: bot:app
  aws:elasticbeanstalk:application:environment:
    FLASK_DEBUG: false
    PYTHONPATH: "/var/app/current:$PYTHONPATH"
```

2. Deploy:
```bash
eb init -p python-3.11 mr_bot
eb create mr_bot-env
eb setenv FLASK_DEBUG=false OPENAI_API_KEY=your-key
```

### Google Cloud Run

```bash
# Build and push to Google Container Registry
gcloud builds submit --tag gcr.io/PROJECT-ID/mr_bot

# Deploy to Cloud Run
gcloud run deploy mr_bot \
  --image gcr.io/PROJECT-ID/mr_bot \
  --platform managed \
  --set-env-vars FLASK_DEBUG=false \
  --set-env-vars OPENAI_API_KEY=your-key
```

### Heroku

```bash
# Create Heroku app
heroku create your-mr_bot-app

# Set environment variables
heroku config:set FLASK_DEBUG=false
heroku config:set OPENAI_API_KEY=your-key

# Deploy
git push heroku main
```

---

## 📊 Monitoring and Logging

### Log Configuration

Create `logging.conf`:
```ini
[loggers]
keys=root,werkzeug

[handlers]
keys=console,file

[formatters]
keys=standard

[logger_root]
level=INFO
handlers=console,file

[logger_werkzeug]
level=INFO
handlers=console,file
qualname=werkzeug
propagate=0

[handler_console]
class=StreamHandler
level=INFO
formatter=standard
args=(sys.stdout,)

[handler_file]
class=FileHandler
level=INFO
formatter=standard
args=('logs/mr_bot.log',)

[formatter_standard]
format=%(asctime)s [%(levelname)s] %(name)s: %(message)s
datefmt=%Y-%m-%d %H:%M:%S
```

### Health Checks

The bot includes a health endpoint:
```bash
curl http://localhost:3978/
# Returns: {"status": "running", "bot_name": "my_bot", ...}
```

### Monitoring with Prometheus (Optional)

```bash
pip install prometheus-flask-exporter
```

Add to `bot.py`:
```python
from prometheus_flask_exporter import PrometheusMetrics
metrics = PrometheusMetrics(app)
```

---

## 🔒 Production Security Hardening

### File Permissions

```bash
# Set secure permissions
chmod 600 config.py
chmod 700 data/
chmod 600 data/sessions/*

# Run as non-root user
useradd -m botuser
chown -R botuser:botuser /path/to/mr_bot
su - botuser
cd /path/to/mr_bot
```

### Firewall Configuration

```bash
# UFW (Ubuntu/Debian)
ufw allow 3978/tcp
ufw allow 443/tcp
ufw enable

# firewalld (CentOS/RHEL)
firewall-cmd --permanent --add-port=3978/tcp
firewall-cmd --permanent --add-service=https
firewall-cmd --reload
```

### Fail2ban (Brute Force Protection)

Create `/etc/fail2ban/jail.local`:
```ini
[mr_bot]
enabled = true
port = http,https
filter = mr_bot
logpath = /path/to/mr_bot/logs/mr_bot.log
maxretry = 5
bantime = 3600
```

---

## 🔄 Backup and Recovery

### Automated Backups

```bash
#!/bin/bash
# backup.sh - Run daily via cron

BACKUP_DIR="/backups/mr_bot"
DATE=$(date +%Y%m%d_%H%M%S)

# Backup session data
tar -czf "$BACKUP_DIR/sessions_$DATE.tar.gz" data/sessions/

# Keep only last 30 days
find $BACKUP_DIR -name "sessions_*.tar.gz" -mtime +30 -delete
```

Add to crontab:
```bash
0 2 * * * /path/to/mr_bot/backup.sh
```

### Recovery

```bash
# Restore from backup
tar -xzf backups/sessions_20260207_020000.tar.gz -C /path/to/mr_bot/
```

---

## 🆘 Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| Port already in use | Use `free_port()` function or change port |
| Permission denied | Check file permissions, run as correct user |
| Module not found | Activate virtual environment, reinstall requirements |
| API key errors | Verify environment variables are set |
| Rate limiting | Check `flask-limiter` is installed |

### Debug Mode

For troubleshooting only:
```bash
export FLASK_DEBUG=true
python bot.py
```

**Remember to disable in production!**

---

## 📞 Support

- **Issues**: GitHub Issues
- **Security**: security@idrak.ai
- **Community**: Discord/Slack (if available)

---

**Project**: mr_bot - Persistent Memory AI Chatbot  
**Organization**: Idrak AI Ltd  
**License**: Open Source - Safe Open Community Project

---

*Last updated: 2026-02-07*
