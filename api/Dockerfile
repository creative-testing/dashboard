FROM python:3.11-slim

# Définir le répertoire de travail
WORKDIR /app

# Installer les dépendances système nécessaires
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copier les fichiers de dépendances
COPY requirements-api.txt .

# Installer les dépendances Python
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements-api.txt

# Copier le reste du code
COPY . .

# Créer le répertoire pour les données locales
RUN mkdir -p /mnt/data

# Exposer le port (configuré via env var PORT)
EXPOSE 10002

# Le CMD sera défini dans docker-compose pour API ou Cron
