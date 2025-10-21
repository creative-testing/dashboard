#!/bin/bash
# Script de démarrage pour Render
# Lance les migrations Alembic puis démarre l'API FastAPI

set -e  # Arrêter immédiatement si une commande échoue

echo "🗄️  Running database migrations..."
alembic upgrade head

echo "✅ Database migrations applied successfully"
echo ""
echo "🚀 Starting FastAPI server..."

# exec remplace le process du script par uvicorn (bonne pratique)
exec uvicorn app.main:app --host 0.0.0.0 --port $PORT
