#!/bin/bash
# Script pour faire un refresh tail rapide avec auto-commit vers GitHub

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
    echo "✅ Refresh terminé!"
    
    # Auto-commit et push vers GitHub
    echo ""
    echo "📤 Push vers GitHub..."
    
    # Copier les fichiers optimisés vers le dossier dashboard
    cp data/optimized/*.json dashboards/optimized/data/optimized/
    
    # Git operations
    git add data/optimized/*.json dashboards/optimized/data/optimized/*.json
    git commit -m "🤖 Auto-refresh data: $(date '+%Y-%m-%d %H:%M') (tail mode)" || echo "Pas de changements à commiter"
    
    # Push seulement si il y a eu un commit
    if [ $? -eq 0 ]; then
        git push origin master
        echo "✅ Données mises à jour sur GitHub!"
    fi
else
    echo "❌ Erreur lors du fetch"
    exit 1
fi