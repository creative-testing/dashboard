#!/bin/bash
# Script pour faire un refresh tail rapide (3 derniers jours)

echo "⚡ Lancement du refresh TAIL (3 derniers jours)"
echo "🕰️ Buffer: 2 heures depuis maintenant"
echo ""

# Mode tail (par défaut)
export FRESHNESS_BUFFER_HOURS=2
export TAIL_BACKFILL_DAYS=3
export RUN_BASELINE=0

# Lancer le fetch (qui inclut déjà la compression)
python3 scripts/production/fetch_with_smart_limits.py

if [ $? -eq 0 ]; then
    echo "✅ Terminé!"
else
    echo "❌ Erreur lors du fetch"
    exit 1
fi