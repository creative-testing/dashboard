#!/usr/bin/env python3
"""
Analyse SIMPLE de nomenclature : compter les slashes
Structure correcte = exactement 4 slashes (5 parties)
"""

import json
from pathlib import Path
from collections import defaultdict

def count_slashes(ad_name):
    """Compte simplement les / dans le nom"""
    return ad_name.count('/')

def main():
    # Charger les données
    data_path = Path(__file__).parent.parent.parent / 'data' / 'current' / 'baseline_90d_daily.json'
    
    print("📊 Analyse SIMPLE : Compter les slashes dans les nomenclatures")
    print("=" * 80)
    
    with open(data_path) as f:
        data = json.load(f)
    
    # Filtrer les pubs depuis le 7 septembre 2025
    ads = [ad for ad in data.get('daily_ads', []) 
           if ad.get('created_time', '') >= '2025-09-07']
    
    print(f"Total : {len(ads)} pubs créées depuis le 7 septembre 2025\n")
    
    # Analyser par compte
    by_account = defaultdict(list)
    for ad in ads:
        account = ad.get('account_name', 'Unknown')
        slashes = count_slashes(ad['ad_name'])
        by_account[account].append({
            'name': ad['ad_name'],
            'slashes': slashes,
            'spend': float(ad.get('spend', 0))
        })
    
    # Statistiques globales
    total_correct = 0
    total_incorrect = 0
    
    print("📋 RÉSULTATS PAR COMPTE")
    print("-" * 80)
    
    account_stats = []
    
    for account, ads_list in sorted(by_account.items()):
        correct = sum(1 for ad in ads_list if ad['slashes'] == 4)
        incorrect = len(ads_list) - correct
        total_correct += correct
        total_incorrect += incorrect
        
        pct = (correct / len(ads_list) * 100) if ads_list else 0
        
        account_stats.append({
            'account': account,
            'total': len(ads_list),
            'correct': correct,
            'incorrect': incorrect,
            'pct': pct,
            'ads': ads_list
        })
    
    # Trier par pourcentage de conformité
    account_stats.sort(key=lambda x: x['pct'], reverse=True)
    
    # Afficher les meilleurs
    print("\n✅ MEILLEURS COMPTES (structure correcte avec 4 slashes):")
    print("-" * 80)
    for stat in account_stats[:10]:
        if stat['pct'] > 0:
            print(f"{stat['account']}: {stat['correct']}/{stat['total']} correct ({stat['pct']:.0f}%)")
            # Montrer un exemple correct
            for ad in stat['ads']:
                if ad['slashes'] == 4:
                    print(f"  ✅ Exemple: {ad['name'][:80]}...")
                    break
    
    # Afficher les pires
    print("\n❌ COMPTES PROBLÉMATIQUES (pas 4 slashes):")
    print("-" * 80)
    for stat in reversed(account_stats[-10:]):
        if stat['pct'] < 100:
            print(f"{stat['account']}: {stat['incorrect']}/{stat['total']} incorrect ({100-stat['pct']:.0f}% mauvais)")
            # Montrer les différents nombres de slashes trouvés
            slash_counts = defaultdict(int)
            examples = {}
            for ad in stat['ads']:
                slash_counts[ad['slashes']] += 1
                if ad['slashes'] not in examples:
                    examples[ad['slashes']] = ad['name']
            
            print(f"  Distribution des slashes:", end="")
            for slashes, count in sorted(slash_counts.items()):
                print(f" {slashes} slash{'es' if slashes != 1 else ''}={count} pubs,", end="")
            print()
            
            # Montrer un exemple problématique
            for slashes, example in sorted(examples.items()):
                if slashes != 4:
                    print(f"  ❌ Exemple ({slashes} slash{'es' if slashes != 1 else ''}): {example[:60]}...")
                    break
    
    # Statistiques détaillées
    print("\n📊 DISTRIBUTION GLOBALE DES SLASHES:")
    print("-" * 80)
    slash_distribution = defaultdict(int)
    for account, ads_list in by_account.items():
        for ad in ads_list:
            slash_distribution[ad['slashes']] += 1
    
    for slashes in sorted(slash_distribution.keys()):
        count = slash_distribution[slashes]
        pct = count / len(ads) * 100
        status = "✅ CORRECT" if slashes == 4 else "❌"
        print(f"{slashes} slashes: {count} pubs ({pct:.1f}%) {status}")
    
    # Résumé final
    print("\n" + "=" * 80)
    print("📈 RÉSUMÉ FINAL")
    print("=" * 80)
    pct_correct = (total_correct / len(ads) * 100) if ads else 0
    print(f"✅ Structure correcte (4 slashes) : {total_correct} pubs ({pct_correct:.1f}%)")
    print(f"❌ Structure incorrecte : {total_incorrect} pubs ({100-pct_correct:.1f}%)")
    
    # Top 5 des comptes avec le plus de pubs incorrectes
    print("\n🚨 TOP 5 COMPTES À CORRIGER (par volume):")
    account_stats.sort(key=lambda x: x['incorrect'], reverse=True)
    for i, stat in enumerate(account_stats[:5], 1):
        if stat['incorrect'] > 0:
            print(f"{i}. {stat['account']}: {stat['incorrect']} pubs incorrectes")

if __name__ == '__main__':
    main()