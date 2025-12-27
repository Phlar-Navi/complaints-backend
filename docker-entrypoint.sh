#!/bin/bash
set -e

echo "======================================"
echo "🚀 Django Multi-tenant on Railway"
echo "======================================"

# Vérifier que PORT est défini
if [ -z "$PORT" ]; then
    echo "⚠️  PORT not set, using default 8000"
    export PORT=8000
fi

echo "📡 Port: $PORT"
echo "📊 Database: ${DATABASE_URL:0:30}..."

# Fonction pour attendre PostgreSQL avec DATABASE_URL
wait_for_postgres() {
    if [ -z "$DATABASE_URL" ]; then
        echo "⚠️  No DATABASE_URL set, skipping database check"
        return 0
    fi

    echo "⏳ Waiting for PostgreSQL..."
    
    python << END
import sys
import time
import os

try:
    import psycopg2
except ImportError:
    print("⚠️  psycopg2 not available, skipping database check")
    sys.exit(0)

database_url = os.environ.get('DATABASE_URL', '')
if not database_url:
    print("⚠️  No DATABASE_URL, skipping")
    sys.exit(0)

max_retries = 30
retry = 0

while retry < max_retries:
    try:
        conn = psycopg2.connect(database_url)
        conn.close()
        print("✅ PostgreSQL is ready!")
        sys.exit(0)
    except Exception as e:
        retry += 1
        if retry < max_retries:
            print(f"⏳ Waiting for PostgreSQL... ({retry}/{max_retries})")
            time.sleep(2)
        else:
            print(f"❌ Could not connect to PostgreSQL: {e}")
            sys.exit(1)
END
}

# Attendre PostgreSQL
wait_for_postgres

# Exécuter les migrations
echo "🔄 Running migrations..."
python manage.py migrate --noinput || {
    echo "⚠️  Migration failed, but continuing..."
}

# Créer le superuser si les variables sont définies
if [ -n "$DJANGO_SUPERUSER_EMAIL" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
    echo "👤 Creating superuser..."
    python manage.py shell << END
from django.contrib.auth import get_user_model
User = get_user_model()

email = "${DJANGO_SUPERUSER_EMAIL}"
password = "${DJANGO_SUPERUSER_PASSWORD}"

if not User.objects.filter(email=email).exists():
    try:
        User.objects.create_superuser(
            email=email,
            password=password,
            full_name="${DJANGO_SUPERUSER_NAME:-Super Admin}"
        )
        print("✅ Superuser created")
    except Exception as e:
        print(f"⚠️  Could not create superuser: {e}")
else:
    print("✅ Superuser already exists")
END
fi

# Collecter les fichiers statiques
echo "📦 Collecting static files..."
python manage.py collectstatic --noinput --clear || {
    echo "⚠️  Static files collection failed (non-critical)"
}

echo ""
echo "======================================"
echo "✅ Initialization complete"
echo "======================================"
echo "🎯 Starting Gunicorn on 0.0.0.0:$PORT"
echo ""

# Lancer Gunicorn - SEULEMENT ICI
exec gunicorn complaintsManager.wsgi:application \
  --bind "0.0.0.0:${PORT}" \
  --workers 4 \
  --threads 2 \
  --timeout 60 \
  --access-logfile - \
  --error-logfile - \
  --log-level info