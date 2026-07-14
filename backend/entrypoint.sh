#!/bin/sh
set -e

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
