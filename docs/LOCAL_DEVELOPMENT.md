# Local Development Guide

## Running the Server
Ensure your virtual environment is active and run:
```bash
python manage.py runserver
```
The application will be available at `http://127.0.0.1:8000`.

## Code Standards
This project strictly follows **PEP 8** compliance. 
- Use explicit imports (no `import *`).
- Ensure all new views and models contain appropriate docstrings.
- Use `get_object_or_404` instead of `.get()` to gracefully handle missing records.

## Handling Static and Media Files
In local development (`DEBUG=True`), Django automatically serves static and media files. 
- Place global CSS/JS in `/static/`.
- User-uploaded files (like product images) are saved to `/media/`.

## Common Commands
- **Make Migrations**: `python manage.py makemigrations`
- **Apply Migrations**: `python manage.py migrate`
- **Collect Static**: `python manage.py collectstatic` (Only needed for production testing)
