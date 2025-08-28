#!/bin/bash

echo "🚀 FETCH EVERYTHING - Récupération complète des données Facebook Ads"
echo "=================================================="
echo ""

# Configuration
export FETCH_DAYS=90

# Couleurs pour l'output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Créer le dossier de logs s'il n'existe pas
mkdir -p logs

# Timestamp pour les logs
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="logs/fetch_everything_${TIMESTAMP}.log"

echo -e "${YELLOW}📅 Configuration:${NC}"
echo "  - Période: $FETCH_DAYS jours"
echo "  - Date de référence: hier"
echo "  - Log: $LOG_FILE"
echo ""

echo -e "${YELLOW}🔄 Lancement du script...${NC}"
echo ""

# Exécuter le script
python3 scripts/production/fetch_everything.py 2>&1 | tee "$LOG_FILE"

# Vérifier le code de retour
if [ ${PIPESTATUS[0]} -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ SUCCESS! Récupération complète terminée${NC}"
    echo ""
    echo "📊 Fichiers générés:"
    echo "  - data/current/baseline_90d_complete.json"
    echo "  - data/current/hybrid_data_3d.json"
    echo "  - data/current/hybrid_data_7d.json"
    echo "  - data/current/hybrid_data_14d.json"
    echo "  - data/current/hybrid_data_30d.json"
    echo "  - data/current/hybrid_data_90d.json"
    echo ""
    echo "📈 Dashboard disponible à: dashboards/current/index.html"
else
    echo ""
    echo -e "❌ ERREUR lors de l'exécution"
    echo "Consultez le log: $LOG_FILE"
    exit 1
fi