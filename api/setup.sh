#!/usr/bin/env bash
# Script de setup automatique pour l'API Creative Testing SaaS
# Usage: bash setup.sh

set -euo pipefail

cd "$(dirname "$0")"

echo "🚀 Setup Creative Testing SaaS API"
echo "===================================="
echo ""

# Couleurs pour output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 1. Venv
echo "📦 Étape 1/7: Environnement virtuel"
if [ ! -d ".venv" ]; then
    echo "   Création du venv..."
    python3 -m venv .venv
    echo -e "   ${GREEN}✓${NC} Venv créé"
else
    echo -e "   ${GREEN}✓${NC} Venv déjà présent"
fi

# 2. Activer venv
echo ""
echo "🔧 Étape 2/7: Activation du venv"
source .venv/bin/activate
echo -e "   ${GREEN}✓${NC} Venv activé"

# 3. Upgrade pip
echo ""
echo "⬆️  Étape 3/7: Mise à jour de pip"
pip install --upgrade pip -q
echo -e "   ${GREEN}✓${NC} pip mis à jour"

# 4. Installer dépendances
echo ""
echo "📥 Étape 4/7: Installation des dépendances"
if [ -f "pyproject.toml" ]; then
    echo "   Installation depuis pyproject.toml..."
    pip install -e . -q
else
    echo "   Installation depuis requirements-api.txt..."
    pip install -r requirements-api.txt -q
    pip install -r ../requirements.txt -q
fi
echo -e "   ${GREEN}✓${NC} Dépendances installées"

# 5. Configuration .env
echo ""
echo "📝 Étape 5/7: Configuration .env"
if [ ! -f ".env" ]; then
    cp .env.example .env

    # Générer clé Fernet
    echo "   Génération clé de chiffrement Fernet..."
    FERNET_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

    # Remplacer dans .env (compatible macOS et Linux)
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s/your-32-byte-fernet-key-CHANGE-ME/$FERNET_KEY/" .env
    else
        sed -i "s/your-32-byte-fernet-key-CHANGE-ME/$FERNET_KEY/" .env
    fi

    echo -e "   ${GREEN}✓${NC} Fichier .env créé avec clé de chiffrement"
    echo -e "   ${YELLOW}⚠${NC}  IMPORTANT: Éditez .env et remplissez:"
    echo "      - DATABASE_URL"
    echo "      - META_APP_SECRET (après rotation!)"
    echo "      - STRIPE_SECRET_KEY"
else
    echo -e "   ${GREEN}✓${NC} Fichier .env déjà présent"
fi

# 6. Docker Compose
echo ""
echo "🐳 Étape 6/7: Vérification Docker"
if command -v docker-compose &> /dev/null || docker compose version &> /dev/null; then
    echo -e "   ${GREEN}✓${NC} Docker Compose disponible"
    echo "   Pour démarrer Postgres + Redis:"
    echo "   → docker-compose up -d"
else
    echo -e "   ${YELLOW}⚠${NC}  Docker Compose non trouvé (optionnel)"
fi

# 7. Alembic migrations
echo ""
echo "🗄️  Étape 7/7: Migrations Alembic"
if [ -f "alembic.ini" ]; then
    # Vérifier si au moins une migration existe
    if ! ls alembic/versions/*.py >/dev/null 2>&1; then
        echo "   Création de la migration initiale..."
        alembic revision --autogenerate -m "Initial schema" || {
            echo -e "   ${YELLOW}⚠${NC}  Échec création migration (normal si DB pas démarrée)"
            echo "      Lancez après avoir démarré docker-compose"
        }
    else
        echo -e "   ${GREEN}✓${NC} Migrations déjà présentes"
    fi

    # Tenter d'appliquer les migrations si DB accessible
    if alembic upgrade head 2>/dev/null; then
        echo -e "   ${GREEN}✓${NC} Migrations appliquées"
    else
        echo -e "   ${YELLOW}⚠${NC}  DB non accessible (lancez docker-compose d'abord)"
    fi
else
    echo -e "   ${RED}✗${NC} alembic.ini manquant"
fi

# 8. Vérification import
echo ""
echo "🔍 Vérification finale"
if python -c "from app.main import app; print('FastAPI import OK')" 2>/dev/null; then
    echo -e "   ${GREEN}✓${NC} FastAPI importe correctement"
else
    echo -e "   ${RED}✗${NC} Erreur d'import (vérifiez les dépendances)"
fi

# Résumé final
echo ""
echo "=========================================="
echo -e "${GREEN}✅ Setup terminé!${NC}"
echo "=========================================="
echo ""
echo "📋 Prochaines étapes:"
echo ""
echo "1. Éditez .env avec vos credentials"
echo "2. Lancez Docker Compose:"
echo "   → docker-compose up -d"
echo ""
echo "3. Créez/appliquez les migrations:"
echo "   → alembic revision --autogenerate -m 'Initial schema'"
echo "   → alembic upgrade head"
echo ""
echo "4. Démarrez l'API:"
echo "   → uvicorn app.main:app --reload"
echo ""
echo "5. Accédez à:"
echo "   → API: http://localhost:8000"
echo "   → Docs: http://localhost:8000/docs"
echo "   → Adminer (DB): http://localhost:8080"
echo ""
echo "📚 Voir README.md pour plus de détails"
