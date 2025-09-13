#!/usr/bin/env python3
"""
Montrer des exemples concrets de nomenclatures
"""

import json
from collections import defaultdict
from pathlib import Path

# Charger les données
data_path = Path(__file__).parent.parent.parent / 'data' / 'current' / 'baseline_90d_daily.json'

with open(data_path) as f:
    data = json.load(f)

ads = [ad for ad in data.get('daily_ads', []) 
       if ad.get('created_time', '') >= '2025-09-07']

# Grouper par nombre de slashes
by_slashes = defaultdict(list)
for ad in ads:
    slashes = ad['ad_name'].count('/')
    by_slashes[slashes].append({
        'name': ad['ad_name'],
        'account': ad.get('account_name', 'Unknown'),
        'spend': float(ad.get('spend', 0))
    })

print('=' * 100)
print('📋 EXEMPLES CONCRETS PAR CATÉGORIE')
print('=' * 100)

# CORRECTS (4 slashes)
print('\n✅ STRUCTURE CORRECTE (4 slashes = 5 parties)')
print('-' * 80)
for ad in sorted(by_slashes[4], key=lambda x: x['spend'], reverse=True)[:8]:
    print(f"📍 {ad['account']}:")
    print(f"   {ad['name']}")
    parts = ad['name'].split('/')
    if len(parts) >= 5:
        print(f"   → Type: '{parts[0].strip()}'")
        print(f"   → Angle: '{parts[1].strip()}'")
        print(f"   → Créateur: '{parts[2].strip()}'")
        print(f"   → Age: '{parts[3].strip()}'")
        print(f"   → Hook: '{parts[4].strip()}'")
    print(f"   💰 Spend: ${ad['spend']:.0f}\n")

# PROBLÈME : 0 slashes
print('\n❌ PROBLÈME : AUCUN SLASH (0 slashes)')
print('-' * 80)
for ad in sorted(by_slashes[0], key=lambda x: x['spend'], reverse=True)[:8]:
    print(f"📍 {ad['account']}: \"{ad['name'][:60]}{'...' if len(ad['name']) > 60 else ''}\"")
    print(f"   💰 Spend: ${ad['spend']:.0f}")

# PROBLÈME : 1 slash
print('\n\n❌ PROBLÈME : 1 SEUL SLASH (2 parties au lieu de 5)')
print('-' * 80)
for ad in by_slashes[1][:5]:
    print(f"📍 {ad['account']}: \"{ad['name']}\"")
    parts = ad['name'].split('/')
    print(f"   → Partie 1: '{parts[0].strip()}'")
    if len(parts) > 1:
        print(f"   → Partie 2: '{parts[1].strip()}'")
    print()

# PROBLÈME : 5 slashes
print('\n❌ PROBLÈME : 5 SLASHES (6 parties au lieu de 5)')
print('-' * 80)
for ad in sorted(by_slashes[5], key=lambda x: x['spend'], reverse=True)[:5]:
    print(f"📍 {ad['account']}:")
    print(f"   {ad['name']}")
    parts = ad['name'].split('/')
    print(f"   → 6 parties trouvées:")
    for i, p in enumerate(parts[:6], 1):
        marker = "⚠️" if i == 6 else "  "
        print(f"     {marker} {i}. '{p.strip()}'")
    print(f"   💰 Spend: ${ad['spend']:.0f}\n")

# Statistiques finales
print('\n' + '=' * 100)
print('📊 RÉSUMÉ')
print('=' * 100)
for slashes in sorted(by_slashes.keys()):
    count = len(by_slashes[slashes])
    pct = count / len(ads) * 100
    status = "✅ CORRECT" if slashes == 4 else "❌"
    print(f"{slashes} slashes: {count} pubs ({pct:.1f}%) {status}")