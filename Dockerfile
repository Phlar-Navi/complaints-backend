# ==============================================================================
# Dockerfile - Django Multi-tenant avec PostgreSQL
# Multi-stage build pour optimiser la taille et la sécurité
# ==============================================================================

# ------------------------------------------------------------------------------
# STAGE 1: Builder - Compilation des dépendances
# ------------------------------------------------------------------------------
FROM python:3.12-slim as builder

# Métadonnées
LABEL maintainer="votre-email@example.com"
LABEL description="Django Multi-tenant Application - Builder Stage"

# Variables d'environnement pour Python
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Installer les dépendances système nécessaires pour la compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    postgresql-client \
    libpq-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Créer un environnement virtuel
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copier requirements et installer les dépendances Python
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --default-timeout=120 -r /tmp/requirements.txt

# ------------------------------------------------------------------------------
# STAGE 2: Runtime - Image finale légère
# ------------------------------------------------------------------------------
FROM python:3.12-slim

# Métadonnées
LABEL maintainer="smrcorp007@gmail.com"
LABEL description="Django Multi-tenant Application - Production"
LABEL version="1.0"

# Variables d'environnement
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DJANGO_SETTINGS_MODULE=complaintsManager.settings \
    PATH="/opt/venv/bin:$PATH"

# Installer uniquement les dépendances runtime PostgreSQL
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Créer un utilisateur non-root pour la sécurité
RUN groupadd -r django && \
    useradd -r -g django -u 1000 -m -s /bin/bash django

# Créer les répertoires nécessaires
RUN mkdir -p /app /app/staticfiles /app/mediafiles /app/logs && \
    chown -R django:django /app

# Copier l'environnement virtuel depuis le builder
COPY --from=builder --chown=django:django /opt/venv /opt/venv

# Définir le répertoire de travail
WORKDIR /app

# Copier le code de l'application
COPY --chown=django:django . /app/

# Copier les scripts d'entrée
COPY --chown=django:django docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Collecter les fichiers statiques (sera fait au démarrage pour les volumes)
# RUN python manage.py collectstatic --noinput

# Changer vers l'utilisateur non-root
USER django

# Exposer le port
EXPOSE 8000

# Healthcheck pour Docker Swarm/Kubernetes
# HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    # CMD curl -f http://localhost:8000/api/health/ || exit 1

# Point d'entrée
ENTRYPOINT ["docker-entrypoint.sh"]

# Commande par défaut
CMD gunicorn complaintsManager.wsgi:application \
  --bind 0.0.0.0:$PORT \
  --workers 4 \
  --threads 2 \
  --timeout 60 \
  --access-logfile - \
  --error-logfile - \
  --log-level info
