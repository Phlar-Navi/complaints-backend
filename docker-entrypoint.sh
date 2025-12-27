#!/bin/bash
# ==============================================================================
# Docker Entrypoint Script - Django Multi-tenant
# Gère l'initialisation, les migrations et le démarrage de l'application
# ==============================================================================

set -e  # Arrêter en cas d'erreur

echo "======================================"
echo "Django Multi-tenant Application"
echo "======================================"

# Fonction pour attendre que PostgreSQL soit prêt
wait_for_postgres() {
    echo "⏳ Attente de PostgreSQL..."
    
    max_attempts=30
    attempt=0
    
    until PGPASSWORD=$DB_PASSWORD psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -c '\q' 2>/dev/null; do
        attempt=$((attempt + 1))
        
        if [ $attempt -eq $max_attempts ]; then
            echo "❌ Échec de la connexion à PostgreSQL après $max_attempts tentatives"
            exit 1
        fi
        
        echo "⏳ PostgreSQL n'est pas encore prêt (tentative $attempt/$max_attempts)..."
        sleep 2
    done
    
    echo "✅ PostgreSQL est prêt !"
}

# Fonction pour créer la base de données si elle n'existe pas
create_database_if_not_exists() {
    echo "🔍 Vérification de l'existence de la base de données..."
    
    if ! PGPASSWORD=$DB_PASSWORD psql -h "$DB_HOST" -U "$DB_USER" -lqt | cut -d \| -f 1 | grep -qw "$DB_NAME"; then
        echo "📦 Création de la base de données $DB_NAME..."
        PGPASSWORD=$DB_PASSWORD psql -h "$DB_HOST" -U "$DB_USER" -c "CREATE DATABASE $DB_NAME;"
        echo "✅ Base de données créée !"
    else
        echo "✅ Base de données existe déjà"
    fi
}

# Fonction pour exécuter les migrations
run_migrations() {
    echo "🔄 Exécution des migrations..."
    
    # Migrations du schema public (shared apps)
    echo "📋 Migrations du schema public..."
    python manage.py migrate_schemas --shared
    
    # Créer le schema public si nécessaire
    echo "📋 Création du tenant public si nécessaire..."
    python manage.py shell <<EOF
from tenants.models import Tenant, Domain
from django.db.utils import IntegrityError

try:
    # Vérifier si le tenant public existe
    tenant = Tenant.objects.filter(schema_name='public').first()
    if not tenant:
        print("Création du tenant public...")
        tenant = Tenant.objects.create(
            schema_name='public',
            name='Plateforme Principale',
            is_active=True
        )
        Domain.objects.create(
            domain='${PUBLIC_DOMAIN:-localhost}',
            tenant=tenant,
            is_primary=True
        )
        print("✅ Tenant public créé")
    else:
        print("✅ Tenant public existe déjà")
except Exception as e:
    print(f"⚠️  Avertissement lors de la création du tenant public: {e}")
EOF
    
    # Migrations des tenants
    echo "📋 Migrations des tenants..."
    python manage.py migrate_schemas --executor=standard
    
    echo "✅ Migrations terminées !"
}

# Fonction pour créer un superutilisateur
create_superuser() {
    echo "👤 Création du superutilisateur..."
    
    python manage.py shell <<EOF
from users.models import CustomUser
from django.db import IntegrityError

try:
    if not CustomUser.objects.filter(email='${DJANGO_SUPERUSER_EMAIL:-admin@example.com}').exists():
        CustomUser.objects.create_superuser(
            email='${DJANGO_SUPERUSER_EMAIL:-admin@example.com}',
            password='${DJANGO_SUPERUSER_PASSWORD:-changeme}',
            full_name='${DJANGO_SUPERUSER_NAME:-Super Admin}',
            role='SUPER_ADMIN'
        )
        print("✅ Superutilisateur créé")
    else:
        print("✅ Superutilisateur existe déjà")
except IntegrityError:
    print("⚠️  Superutilisateur existe déjà")
except Exception as e:
    print(f"⚠️  Erreur lors de la création du superutilisateur: {e}")
EOF
}

# Fonction pour collecter les fichiers statiques
collect_static() {
    echo "📦 Collection des fichiers statiques..."
    python manage.py collectstatic --noinput --clear
    echo "✅ Fichiers statiques collectés !"
}

# Fonction pour créer les répertoires nécessaires
create_directories() {
    echo "📁 Création des répertoires nécessaires..."
    mkdir -p /app/staticfiles /app/mediafiles /app/logs
    echo "✅ Répertoires créés !"
}

# ==============================================================================
# EXÉCUTION PRINCIPALE
# ==============================================================================

echo ""
echo "🚀 Démarrage de l'initialisation..."
echo ""

# Créer les répertoires
create_directories

# Attendre PostgreSQL
wait_for_postgres

# Créer la base de données si nécessaire
create_database_if_not_exists

# Exécuter les migrations
run_migrations

# Créer le superutilisateur
if [ "${CREATE_SUPERUSER:-true}" = "true" ]; then
    create_superuser
fi

# Collecter les fichiers statiques
if [ "${COLLECT_STATIC:-true}" = "true" ]; then
    collect_static
fi

echo ""
echo "======================================"
echo "✅ Initialisation terminée avec succès"
echo "======================================"
echo ""

# Afficher les informations de démarrage
echo "📊 Configuration:"
echo "   - Base de données: $DB_NAME@$DB_HOST"
echo "   - Debug mode: ${DEBUG:-False}"
echo "   - Workers: ${GUNICORN_WORKERS:-4}"
echo ""

# Exécuter la commande passée en argument (CMD du Dockerfile)
echo "🚀 Démarrage de l'application..."
exec "$@"