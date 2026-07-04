# 🚀 Deployment Guide

## Production Checklist
Before deploying to a production server, ensure the following are configured in your environment:
- `DEBUG=False`
- `SECRET_KEY` (must be long, random, and cryptographically secure)
- `ALLOWED_HOSTS` (comma-separated list of your production domains)

## Static Files
In production, Django does not serve static files. You must collect them:
```bash
python manage.py collectstatic --noinput
```
We recommend using **WhiteNoise** or configuring your reverse proxy (Nginx) to serve the `/assets/` directory.

## Web Server setup (Gunicorn + Nginx)
1. Install Gunicorn: `pip install gunicorn`
2. Run the WSGI server:
   ```bash
   gunicorn shoppingbuddy.wsgi:application --bind 0.0.0.0:8000 --workers 3
   ```
3. Route incoming internet traffic to port 8000 via Nginx.

## Database
We heavily recommend migrating from the development `SQLite3` database to a robust relational database like **PostgreSQL** or **MySQL** before launching to users.
