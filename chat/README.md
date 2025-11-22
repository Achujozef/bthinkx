# Production Chat System - Setup & Deployment Guide

A real-time chat system for Django with WebSocket support, featuring personal and group chats, formal email-style messages, typing indicators, read receipts, and file attachments.

## Features

- **Personal (1:1) Chat**: Direct messaging between users
- **Group Chat**: Multi-user chat rooms with admin controls
- **Message Types**:
  - **Casual**: Standard chat bubbles (inline)
  - **Formal**: Email-style messages with subject, to, cc fields
- **Real-time Features**:
  - Live message delivery via WebSockets
  - Typing indicators
  - Read receipts
  - Online/offline status
- **File Attachments**: Images, videos, documents
- **Message History**: Pagination with "load more"
- **Responsive Design**: Mobile-friendly interface

## Architecture

```
┌─────────────┐     WebSocket      ┌──────────────┐
│   Browser   │ ←─────────────────→│ Django       │
│             │                     │ Channels     │
└─────────────┘                     └──────────────┘
                                           │
                                           ↓
                                    ┌──────────────┐
                                    │    Redis     │
                                    │ Channel Layer│
                                    └──────────────┘
                                           │
                                           ↓
                                    ┌──────────────┐
                                    │ PostgreSQL   │
                                    │   Database   │
                                    └──────────────┘
```

## Installation

### 1. Prerequisites

```bash
# Python 3.9+
python --version

# PostgreSQL 13+
psql --version

# Redis 6+
redis-cli --version
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

**requirements.txt:**
```
Django==4.2.9
channels==4.0.0
channels-redis==4.1.0
daphne==4.0.0
redis==5.0.1
psycopg2-binary==2.9.9
Pillow==10.1.0
python-dotenv==1.0.0
gunicorn==21.2.0
uvicorn[standard]==0.25.0
```

### 3. Database Configuration

**settings.py:**
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'bthinkx'),
        'USER': os.environ.get('DB_USER', 'postgres'),
        'PASSWORD': os.environ.get('DB_PASSWORD', ''),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5432'),
    }
}
```

Create database:
```bash
createdb bthinkx
```

### 4. Redis Configuration

**settings.py:**
```python
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [(os.environ.get('REDIS_HOST', 'localhost'), 6379)],
        },
    },
}
```

Start Redis:
```bash
# macOS/Linux
redis-server

# Docker
docker run -d -p 6379:6379 redis:7-alpine
```

### 5. Django Settings

Add to **settings.py:**

```python
INSTALLED_APPS = [
    'daphne',  # Must be first
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'channels',
    'chat',
    # ... other apps
]

# ASGI Application
ASGI_APPLICATION = 'project.asgi.application'

# WebSocket
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [('localhost', 6379)],
        },
    },
}

# Media Files (for attachments)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Security (Production)
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
```

### 6. URL Configuration

**project/urls.py:**
```python
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('chat/', include('chat.urls')),
    # ... other URLs
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

### 7. Run Migrations

```bash
python manage.py makemigrations chat
python manage.py migrate
```

### 8. Create Superuser

```bash
python manage.py createsuperuser
```

## Running Locally

### Development Server

```bash
# Start Redis
redis-server

# Run Django with Daphne (ASGI server)
daphne -b 0.0.0.0 -p 8000 project.asgi:application

# Or use manage.py (uses Daphne automatically)
python manage.py runserver
```

Visit: http://localhost:8000/chat/

## Production Deployment

### Option 1: Nginx + Uvicorn/Daphne

**1. Install Uvicorn:**
```bash
pip install uvicorn[standard]
```

**2. Run ASGI Server:**
```bash
uvicorn project.asgi:application --host 0.0.0.0 --port 8000 --workers 4
```

**3. Nginx Configuration:**

**/etc/nginx/sites-available/bthinkx:**
```nginx
upstream django {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name your-domain.com;
    
    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    # SSL Configuration
    ssl_certificate /path/to/fullchain.pem;
    ssl_certificate_key /path/to/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    
    # Security Headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    
    client_max_body_size 20M;
    
    location / {
        proxy_pass http://django;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support
        proxy_read_timeout 86400;
        proxy_buffering off;
    }
    
    location /static/ {
        alias /path/to/your/staticfiles/;
        expires 30d;
    }
    
    location /media/ {
        alias /path/to/your/media/;
        expires 30d;
    }
}
```

**4. Enable Site:**
```bash
sudo ln -s /etc/nginx/sites-available/bthinkx /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### Option 2: Systemd Service

**1. Create Service File:**

**/etc/systemd/system/bthinkx.service:**
```ini
[Unit]
Description=BThinkX Chat ASGI
After=network.target redis.service postgresql.service

[Service]
Type=notify
User=www-data
Group=www-data
WorkingDirectory=/path/to/project
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/uvicorn project.asgi:application \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 4 \
    --log-level info
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**2. Start Service:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable bthinkx
sudo systemctl start bthinkx
sudo systemctl status bthinkx
```

### Option 3: Docker Deployment

**Dockerfile:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python manage.py collectstatic --no-input

EXPOSE 8000

CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "project.asgi:application"]
```

**docker-compose.yml:**
```yaml
version: '3.8'

services:
  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: bthinkx
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: secure_password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    
  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
  
  web:
    build: .
    command: daphne -b 0.0.0.0 -p 8000 project.asgi:application
    volumes:
      - .:/app
      - static_volume:/app/staticfiles
      - media_volume:/app/media
    ports:
      - "8000:8000"
    depends_on:
      - db
      - redis
    environment:
      - DEBUG=False
      - DB_NAME=bthinkx
      - DB_USER=postgres
      - DB_PASSWORD=secure_password
      - DB_HOST=db
      - DB_PORT=5432
      - REDIS_HOST=redis

volumes:
  postgres_data:
  redis_data:
  static_volume:
  media_volume:
```

**Run:**
```bash
docker-compose up -d
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py createsuperuser
```

## Environment Variables

Create `.env` file:
```bash
# Django
SECRET_KEY=your-secret-key-here
DEBUG=False
ALLOWED_HOSTS=your-domain.com,www.your-domain.com

# Database
DB_NAME=bthinkx
DB_USER=postgres
DB_PASSWORD=secure_password
DB_HOST=localhost
DB_PORT=5432

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# Media Storage (AWS S3 - Optional)
USE_S3=True
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
AWS_STORAGE_BUCKET_NAME=your-bucket
AWS_S3_REGION_NAME=us-east-1
```

## S3 Media Storage (Optional)

**1. Install:**
```bash
pip install django-storages boto3
```

**2. Configure settings.py:**
```python
if os.environ.get('USE_S3') == 'True':
    # AWS S3
    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
    AWS_STORAGE_BUCKET_NAME = os.environ.get('AWS_STORAGE_BUCKET_NAME')
    AWS_S3_REGION_NAME = os.environ.get('AWS_S3_REGION_NAME', 'us-east-1')
    AWS_S3_CUSTOM_DOMAIN = f'{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com'
    AWS_DEFAULT_ACL = 'public-read'
    AWS_S3_OBJECT_PARAMETERS = {'CacheControl': 'max-age=86400'}
    
    # Media files
    DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
    MEDIA_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/media/'
```

## Monitoring & Logging

**1. Setup Logging:**

**settings.py:**
```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/var/log/bthinkx/chat.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'chat': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
```

**2. Monitor WebSocket Connections:**
```bash
# Redis CLI
redis-cli
> PUBSUB CHANNELS
> PUBSUB NUMSUB channel_name
```

## Performance Optimization

### 1. Database Indexing
Already included in models with `db_index=True` and composite indexes.

### 2. Redis Connection Pool
```python
# settings.py
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [('localhost', 6379)],
            'capacity': 1500,
            'expiry': 10,
        },
    },
}
```

### 3. Message Pagination
Implemented with `load_history` WebSocket message - loads 50 messages at a time.

### 4. Typing Indicator Cleanup
Run periodic task to clean old indicators:
```python
# In consumer or management command
TypingIndicator.cleanup_old(seconds=10)
```

## Security Checklist

- [x] HTTPS/WSS encryption
- [x] CSRF protection on all forms
- [x] User authentication required
- [x] Permission checks on room access
- [x] File upload validation
- [x] XSS protection (HTML escaping)
- [x] SQL injection prevention (ORM)
- [x] Rate limiting (consider django-ratelimit)
- [x] Security headers (Nginx)

## Troubleshooting

### WebSocket Connection Failed
```bash
# Check Redis
redis-cli ping

# Check Daphne/Uvicorn logs
journalctl -u bthinkx -f

# Test WebSocket
wscat -c ws://localhost:8000/ws/chat/ROOM_ID/
```

### Messages Not Appearing
- Check browser console for errors
- Verify WebSocket connection (Network tab)
- Check Redis channel layer: `redis-cli PUBSUB CHANNELS`

### File Upload Issues
- Check `MEDIA_ROOT` permissions
- Verify `client_max_body_size` in Nginx
- Check Django `FILE_UPLOAD_MAX_MEMORY_SIZE`

## Testing

```bash
# Run tests
python manage.py test chat

# Load test WebSockets
pip install locust
locust -f load_test.py
```

## Backup Strategy

```bash
# Database backup
pg_dump bthinkx > backup_$(date +%Y%m%d).sql

# Media files backup
tar -czf media_backup_$(date +%Y%m%d).tar.gz media/

# Restore
psql bthinkx < backup_20240101.sql
tar -xzf media_backup_20240101.tar.gz
```

## Support

For issues, check:
1. Application logs: `/var/log/bthinkx/`
2. Nginx logs: `/var/log/nginx/error.log`
3. Redis logs: `redis-cli monitor`
4. Django debug toolbar (development only)

---

**Production Ready:** This system is designed for production use with proper error handling, reconnection logic, security measures, and scalability considerations.