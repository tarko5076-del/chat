#!/bin/sh
set -e

echo "=== Resto AI Backend Entrypoint ==="

echo "Enabling pgvector extension (if PostgreSQL)..."
python -c "
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django.conf
# Only attempt pgvector if using PostgreSQL
db_engine = django.conf.settings.DATABASES['default']['ENGINE']
if 'postgresql' in db_engine:
    django.setup()
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute('CREATE EXTENSION IF NOT EXISTS vector')
        print('  ✓ pgvector extension enabled')
else:
    print('  (not PostgreSQL — skipping)')
" 2>&1 || echo "  (pgvector skipped)"

echo "Running migrations..."
python manage.py migrate --noinput
echo "  ✓ Migrations complete"

if [ "${FORCE_REFRESH:-false}" = "true" ]; then
    echo "FORCE_REFRESH enabled. Re-seeding menu and knowledge base..."
    python manage.py seed_menu --force
    python manage.py seed_knowledge --force
    echo "  ✓ Re-seed complete"
else
    echo "Seeding menu items (if empty)..."
    python manage.py seed_menu
    echo "  ✓ Menu seeding done"

    echo "Seeding knowledge base (skips if already seeded)..."
    python manage.py seed_knowledge
    echo "  ✓ Knowledge base seeding done"
fi

echo "Collecting static files..."
python manage.py collectstatic --noinput 2>/dev/null || echo "  (static files skipped)"

echo "=== Starting server ==="
exec "$@"
