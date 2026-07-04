# Installation Guide

## Prerequisites
- Python 3.10+
- pip

## Step 1: Clone the Repository
```bash
git clone <repository-url>
cd shoppingbuddy
```

## Step 2: Create a Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`
```

## Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

## Step 4: Environment Variables
Copy the example environment file and fill in your secrets:
```bash
cp .env.example .env
```
Ensure you generate a secure `SECRET_KEY` and do not commit `.env`.

## Step 5: Database Setup
Run the initial migrations to set up your SQLite database:
```bash
python manage.py makemigrations
python manage.py migrate
```

## Step 6: Create a Superuser
```bash
python manage.py createsuperuser
```
