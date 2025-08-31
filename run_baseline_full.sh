#!/bin/bash
# Script pour faire un refresh BASELINE complet (90 jours)
# À lancer 1 fois par nuit ou manuellement

echo "📚 Lancement du refresh BASELINE COMPLET (90 jours)"
echo "🕰️ Buffer: 2 heures depuis maintenant"
echo "⚠️ ATTENTION: Ceci peut prendre 30-45 minutes"
echo ""

# Mode baseline complet
export FRESHNESS_BUFFER_HOURS=2
export RUN_BASELINE=1
export FETCH_DAYS=90

# Timeout long pour baseline (qui inclut déjà la compression)
timeout 50m python3 scripts/production/fetch_with_smart_limits.py

if [ $? -eq 0 ]; then
    echo "✅ Baseline complet terminé!"
else
    echo "❌ Erreur lors du fetch baseline"
    exit 1
fi