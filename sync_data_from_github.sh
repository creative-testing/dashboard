#!/bin/bash
# Synchronise les données optimisées depuis GitHub Pages vers le local
# Pour avoir des données fraîches en développement local

echo "🔄 Synchronisation des données depuis GitHub..."
echo "================================================"

# URL de base de GitHub Pages
BASE_URL="https://fred1433.github.io/creative-testing-dashboard/data/optimized"

# Créer le dossier si nécessaire
mkdir -p docs/data/optimized

# Liste des fichiers à synchroniser
FILES=(
    "3d_compressed.json"
    "7d_compressed.json"
    "14d_compressed.json"
    "30d_compressed.json"
    "90d_compressed.json"
    "prev_week_compressed.json"
    "meta_v1.json"
)

# Télécharger chaque fichier
for file in "${FILES[@]}"; do
    echo "📥 Downloading $file..."
    curl -s -o "docs/data/optimized/$file" "$BASE_URL/$file"
    if [ $? -eq 0 ]; then
        echo "   ✅ $file"
    else
        echo "   ⚠️ Failed to download $file"
    fi
done

echo ""
echo "🔍 Vérification des dates..."
# Extraire et afficher la date des données
if [ -f "docs/data/optimized/meta_v1.json" ]; then
    DATA_DATE=$(grep -o '"data_max_date":"[^"]*"' docs/data/optimized/meta_v1.json | cut -d'"' -f4)
    echo "📅 Date des données: $DATA_DATE"
    
    # Calculer le retard
    if [ ! -z "$DATA_DATE" ]; then
        DAYS_AGO=$(( ($(date +%s) - $(date -j -f "%Y-%m-%d" "$DATA_DATE" +%s 2>/dev/null || date -d "$DATA_DATE" +%s)) / 86400 ))
        if [ $DAYS_AGO -eq 0 ]; then
            echo "✅ Données du jour !"
        elif [ $DAYS_AGO -eq 1 ]; then
            echo "✅ Données d'hier (normal, exclude today)"
        else
            echo "⚠️ Données de $DAYS_AGO jours"
        fi
    fi
fi

echo ""
echo "✅ Synchronisation terminée !"
echo ""
echo "🚀 Pour lancer le dashboard local avec les données fraîches:"
echo "   python -m http.server 8080"
echo "   Puis ouvrir: http://localhost:8080/docs/index_full.html"