#!/bin/bash

# Script pour télécharger le baseline depuis GitHub (pour avoir les données historiques en local)
# Cela permet d'avoir les données de la semaine précédente pour les comparaisons

echo "📥 Téléchargement du baseline depuis GitHub..."

# Créer le dossier si nécessaire
mkdir -p data/current

# Télécharger le baseline compressé depuis la release GitHub
if gh release download baseline -p "baseline_90d_daily.json.zst" -D data/current --clobber 2>/dev/null; then
    echo "✅ Baseline téléchargé depuis GitHub"
    
    # Décompresser
    echo "📦 Décompression..."
    if zstd -d -f data/current/baseline_90d_daily.json.zst -o data/current/baseline_90d_daily.json; then
        echo "✅ Baseline décompressé avec succès"
        
        # Nettoyer le fichier compressé
        rm data/current/baseline_90d_daily.json.zst
        
        # Afficher la taille
        SIZE=$(du -h data/current/baseline_90d_daily.json | cut -f1)
        LINES=$(wc -l < data/current/baseline_90d_daily.json)
        echo "📊 Baseline: $SIZE, $LINES lignes"
        
        # Vérifier les dates
        echo "📅 Vérification des dates dans le baseline..."
        python3 -c "
import json
from datetime import datetime, timedelta

with open('data/current/baseline_90d_daily.json', 'r') as f:
    data = json.load(f)
    
if 'daily_ads' in data and data['daily_ads']:
    dates = [ad.get('date') for ad in data['daily_ads'] if ad.get('date')]
    if dates:
        dates = sorted(set(dates))
        print(f'  Date min: {dates[0]}')
        print(f'  Date max: {dates[-1]}')
        print(f'  Nombre de jours uniques: {len(dates)}')
        
        # Vérifier si on a la semaine précédente
        today = datetime.now()
        week_ago = (today - timedelta(days=7)).strftime('%Y-%m-%d')
        two_weeks_ago = (today - timedelta(days=14)).strftime('%Y-%m-%d')
        
        has_prev_week = any(two_weeks_ago <= d <= week_ago for d in dates)
        if has_prev_week:
            print('  ✅ Les données de la semaine précédente sont présentes')
        else:
            print('  ⚠️ Les données de la semaine précédente sont absentes')
else:
    print('  ⚠️ Aucune donnée dans le baseline')
"
        
        echo ""
        echo "✅ Baseline prêt ! Vous pouvez maintenant lancer refresh_local.sh"
        echo "   Les fichiers prev_week seront générés automatiquement"
    else
        echo "❌ Erreur lors de la décompression"
        exit 1
    fi
else
    echo "❌ Impossible de télécharger le baseline depuis GitHub"
    echo "   Vérifiez que vous êtes connecté avec 'gh auth login'"
    exit 1
fi