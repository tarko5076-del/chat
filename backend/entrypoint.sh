#!/bin/sh
set -e

echo "Enabling pgvector extension..."
python -c "
import django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from django.db import connection
with connection.cursor() as cursor:
    cursor.execute('CREATE EXTENSION IF NOT EXISTS vector')
    print('✓ pgvector extension enabled')
"

echo "Running migrations..."
python manage.py migrate --noinput

echo "Seeding menu items..."
python manage.py seed_menu --noinput 2>/dev/null || true

echo "Seeding knowledge base..."
python manage.py seed_knowledge --noinput 2>/dev/null || true

echo "Collecting static files..."
python manage.py collectstatic --noinput 2>/dev/null || true

echo "Starting server..."
exec "$@"
