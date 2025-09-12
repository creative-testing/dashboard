#!/bin/bash
# Script pour déployer et vérifier que GitHub Pages est à jour

echo "🚀 Déploiement vers GitHub Pages..."

# 1. Push les changements
git push origin master

# 2. Attendre un peu
echo "⏳ Attente propagation GitHub Pages (2 min)..."
sleep 120

# 3. Vérifier que c'est déployé
TIMESTAMP=$(date +%s)
TEST_URL="https://fred1433.github.io/creative-testing-dashboard/index_full.html?v=$TIMESTAMP"

echo "🔍 Vérification du déploiement..."

# Chercher un élément unique du nouveau code
if curl -s "$TEST_URL" | grep -q "confidence-badge"; then
    echo "✅ SUCCÈS! Nouvelle version déployée"
    echo "📍 URL: $TEST_URL"
    open "$TEST_URL"  # Ouvre automatiquement
else
    echo "❌ ÉCHEC! Ancienne version encore en ligne"
    echo "Solutions:"
    echo "1. Attendre encore 2-3 minutes"
    echo "2. Vérifier https://github.com/fred1433/creative-testing-dashboard/settings/pages"
    echo "3. Forcer avec: git commit --allow-empty -m 'force deploy' && git push"
fi