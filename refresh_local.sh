#!/bin/bash
# Script pour rafraîchir les données localement (simule le workflow GitHub Actions)

echo "🚀 Rafraîchissement local des données..."

# 1. Fetch des données (5 jours pour éviter les trous)
echo "📥 Fetch des données (5 derniers jours)..."
TAIL_BACKFILL_DAYS=5 FRESHNESS_BUFFER_HOURS=1 python3 scripts/production/fetch_with_smart_limits.py

# 2. Transform en format columnar
echo "🗜️ Transformation en format columnar..."
python3 scripts/transform_to_columnar.py

# 3. Copier vers docs
echo "📋 Copie vers docs/data/optimized..."
mkdir -p docs/data/optimized
cp data/optimized/*.json docs/data/optimized/

echo "✅ Rafraîchissement terminé !"
echo "📊 Ouvrir le dashboard : http://localhost:8080/index_full.html"