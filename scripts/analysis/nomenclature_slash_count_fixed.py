#!/usr/bin/env python3
"""
Analyse SIMPLE de nomenclature : compter les slashes
MAIS en gérant le cas spécial "N/A"
"""

import json
import re
from pathlib import Path
from collections import defaultdict

def count_real_slashes(ad_name):
    """
    Compte les vrais slashes séparateurs
    en traitant "N/A" comme un seul élément
    """
    # Remplacer temporairement N/A par un placeholder
    temp = ad_name.replace('N/A', '{{NA}}').replace('n/a', '{{NA}}')
    
    # Compter les slashes
    slashes = temp.count('/')
    
    return slashes

def get_real_parts(ad_name):
    """
    Récupère les vraies parties en gérant N/A
    """
    # Remplacer temporairement N/A
    temp = ad_name.replace('N/A', '{{NA}}').replace('n/a', '{{NA}}')
    
    # Splitter
    parts = temp.split('/')
    
    # Restaurer N/A
    parts = [p.replace('{{NA}}', 'N/A') for p in parts]
    
    return [p.strip() for p in parts if p.strip()]

def main():
    # Charger les données
    data_path = Path(__file__).parent.parent.parent / 'data' / 'current' / 'baseline_90d_daily.json'
    
    print("📊 Analyse CORRIGÉE : Compter les slashes (en gérant N/A)")
    print("=" * 80)
    
    with open(data_path) as f:
        data = json.load(f)
    
    # Filtrer les pubs depuis le 7 septembre 2025
    ads = [ad for ad in data.get('daily_ads', []) 
           if ad.get('created_time', '') >= '2025-09-07']
    
    print(f"Total : {len(ads)} pubs créées depuis le 7 septembre 2025\n")
    
    # Analyser
    by_slashes = defaultdict(list)
    na_cases = []
    
    for ad in ads:
        name = ad['ad_name']
        slashes = count_real_slashes(name)
        
        # Détecter les cas avec N/A
        if 'N/A' in name or 'n/a' in name:
            na_cases.append({
                'name': name,
                'account': ad.get('account_name', 'Unknown'),
                'slashes': slashes,
                'spend': float(ad.get('spend', 0))
            })
        
        by_slashes[slashes].append({
            'name': name,
            'account': ad.get('account_name', 'Unknown'),
            'spend': float(ad.get('spend', 0))
        })
    
    # Statistiques
    print("📊 DISTRIBUTION DES SLASHES (corrigée pour N/A):")
    print("-" * 80)
    
    for slashes in sorted(by_slashes.keys()):
        count = len(by_slashes[slashes])
        pct = count / len(ads) * 100
        status = "✅ CORRECT" if slashes == 4 else "❌"
        print(f"{slashes} slashes: {count} pubs ({pct:.1f}%) {status}")
    
    # Montrer les cas N/A qui étaient mal comptés
    print("\n🔍 CAS AVEC 'N/A' (maintenant correctement comptés):")
    print("-" * 80)
    
    for case in sorted(na_cases, key=lambda x: x['spend'], reverse=True)[:10]:
        parts = get_real_parts(case['name'])
        status = "✅" if case['slashes'] == 4 else "❌"
        
        print(f"\n{status} {case['account']}:")
        print(f"   {case['name']}")
        print(f"   → {len(parts)} parties détectées: ", end="")
        for i, p in enumerate(parts[:6], 1):
            print(f"{i}.'{p}' ", end="")
        print(f"\n   💰 Spend: ${case['spend']:.0f}")
    
    # Exemples de vrais problèmes (sans N/A)
    print("\n\n❌ VRAIS PROBLÈMES (pas liés à N/A):")
    print("-" * 80)
    
    # 0 slashes
    print("\n0 SLASHES:")
    for ad in sorted(by_slashes[0], key=lambda x: x['spend'], reverse=True)[:5]:
        if 'N/A' not in ad['name'] and 'n/a' not in ad['name']:
            print(f"  • {ad['account']}: \"{ad['name'][:50]}...\" (${ad['spend']:.0f})")
    
    # 5+ slashes sans N/A
    print("\n5+ SLASHES (sans N/A dans le nom):")
    for slashes in [5, 6, 7]:
        if slashes in by_slashes:
            for ad in by_slashes[slashes][:3]:
                if 'N/A' not in ad['name'] and 'n/a' not in ad['name']:
                    parts = ad['name'].split('/')
                    print(f"  • {ad['account']}: {len(parts)} parties")
                    print(f"    {ad['name'][:80]}...")
                    break
    
    # Résumé final
    correct = len(by_slashes[4])
    incorrect = len(ads) - correct
    pct_correct = (correct / len(ads) * 100) if ads else 0
    
    print("\n" + "=" * 80)
    print("📈 RÉSUMÉ FINAL (CORRIGÉ)")
    print("=" * 80)
    print(f"✅ Structure correcte (4 slashes) : {correct} pubs ({pct_correct:.1f}%)")
    print(f"❌ Structure incorrecte : {incorrect} pubs ({100-pct_correct:.1f}%)")
    
    # Comparer avec l'ancienne méthode
    old_method_5_slashes = sum(1 for ad in ads if ad['ad_name'].count('/') == 5)
    fixed_na_cases = sum(1 for ad in ads if ad['ad_name'].count('/') == 5 and ('N/A' in ad['ad_name'] or 'n/a' in ad['ad_name']))
    
    print(f"\n📝 Impact de la correction N/A:")
    print(f"   Avant: {old_method_5_slashes} pubs avec 5 slashes (incorrectes)")
    print(f"   Dont {fixed_na_cases} étaient des faux positifs à cause de 'N/A'")
    print(f"   Vrais problèmes: {old_method_5_slashes - fixed_na_cases} pubs avec trop de parties")

if __name__ == '__main__':
    main()