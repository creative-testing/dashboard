#!/bin/bash
# Script pour faire un refresh BASELINE complet avec auto-commit vers GitHub

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
    
    # Auto-commit et push vers GitHub
    echo ""
    echo "📤 Push vers GitHub..."
    
    # Git operations - removed cp to non-existent dashboards/ directory
    git add data/optimized/*.json
    git commit -m "🤖 Auto-refresh data: $(date '+%Y-%m-%d %H:%M') (baseline 90d)" || echo "Pas de changements à commiter"
    
    # Push seulement si il y a eu un commit
    if [ $? -eq 0 ]; then
        git push origin master
        echo "✅ Données mises à jour sur GitHub!"
    fi
else
    echo "❌ Erreur lors du fetch baseline"
    exit 1
fi