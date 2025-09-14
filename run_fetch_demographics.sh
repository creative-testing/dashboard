#!/bin/bash
# Script pour fetcher les données démographiques (age/gender breakdowns)
# À exécuter 2-4 fois par jour via GitHub Actions

set -e

echo "🔬 Fetch Demographics - Age/Gender Breakdowns"
echo "============================================"
date

# Configuration
export DEVELOPMENT_MODE=1  # 1 = Development tier (200 calls/hour)

# Charger les variables d'environnement
if [ -f .env ]; then
    source .env
fi

# Vérifier que le token existe (chercher les deux noms possibles)
if [ -z "$META_ACCESS_TOKEN" ] && [ -z "$FACEBOOK_ACCESS_TOKEN" ]; then
    echo "❌ ERROR: No access token found (META_ACCESS_TOKEN or FACEBOOK_ACCESS_TOKEN)"
    exit 1
fi

# Utiliser le token disponible
if [ -z "$META_ACCESS_TOKEN" ] && [ -n "$FACEBOOK_ACCESS_TOKEN" ]; then
    export META_ACCESS_TOKEN="$FACEBOOK_ACCESS_TOKEN"
fi

# Créer le dossier de sortie
mkdir -p data/demographics

# Lancer le fetch avec timeout généreux (45 minutes)
echo ""
echo "🚀 Starting demographics fetch..."
echo "⏰ Timeout: 45 minutes"
echo ""

timeout 2700 python scripts/production/fetch_demographics.py

# Vérifier le résultat
if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Demographics fetch completed successfully!"
    
    # Afficher un résumé des fichiers créés
    echo ""
    echo "📊 Files created:"
    find data/demographics -name "*.json" -type f -exec ls -lh {} \; | tail -20
    
    # Compter les segments totaux
    echo ""
    echo "📈 Total segments:"
    find data/demographics -name "*.json" -type f -exec grep -c '"age":' {} \; | paste -sd+ | bc || echo "0"
    
else
    echo ""
    echo "⚠️ Demographics fetch completed with warnings or errors"
fi

echo ""
echo "📁 Output directory: data/demographics/"
echo "🕐 Completed at: $(date)"