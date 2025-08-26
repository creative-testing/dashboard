#!/usr/bin/env python3
"""
Investigation de l'incohérence entre 30j et 90j
"""
import json
from collections import defaultdict

def investigate_discrepancy():
    """Compare les données 30j vs 90j pour comprendre l'incohérence"""
    
    print("🔍 INVESTIGATION INCOHÉRENCE 30J vs 90J")
    print("=" * 70)
    
    # Charger les données
    with open('hybrid_data_30d.json', 'r') as f:
        data_30d = json.load(f)
    
    with open('hybrid_data_90d.json', 'r') as f:
        data_90d = json.load(f)
    
    ads_30d = data_30d['ads']
    ads_90d = data_90d['ads']
    
    print(f"30 jours: {len(ads_30d)} annonces, ${sum(ad['spend'] for ad in ads_30d):,.0f} MXN")
    print(f"90 jours: {len(ads_90d)} annonces, ${sum(ad['spend'] for ad in ads_90d):,.0f} MXN")
    
    # 1. Comparer les comptes
    print(f"\n📊 ANALYSE DES COMPTES")
    print("-" * 40)
    
    accounts_30d = defaultdict(float)
    accounts_90d = defaultdict(float)
    
    for ad in ads_30d:
        accounts_30d[ad['account_name']] += ad['spend']
    
    for ad in ads_90d:
        accounts_90d[ad['account_name']] += ad['spend']
    
    # Comptes présents dans 30j mais absents dans 90j
    missing_in_90d = set(accounts_30d.keys()) - set(accounts_90d.keys())
    if missing_in_90d:
        print(f"⚠️  Comptes présents dans 30j mais ABSENTS dans 90j:")
        for acc in missing_in_90d:
            print(f"  • {acc}: ${accounts_30d[acc]:,.0f} MXN")
    
    # Nouveaux comptes dans 90j
    new_in_90d = set(accounts_90d.keys()) - set(accounts_30d.keys())
    if new_in_90d:
        print(f"\n✅ Nouveaux comptes dans 90j:")
        for acc in new_in_90d:
            print(f"  • {acc}: ${accounts_90d[acc]:,.0f} MXN")
    
    # Top 5 de chaque période
    print(f"\n💰 TOP 5 COMPTES - COMPARAISON")
    print("-" * 40)
    
    top_30d = sorted(accounts_30d.items(), key=lambda x: x[1], reverse=True)[:5]
    top_90d = sorted(accounts_90d.items(), key=lambda x: x[1], reverse=True)[:5]
    
    print("30 JOURS:")
    for name, spend in top_30d:
        print(f"  {name[:25]:25} ${spend:8,.0f}")
    
    print("\n90 JOURS:")
    for name, spend in top_90d:
        print(f"  {name[:25]:25} ${spend:8,.0f}")
        
    # 2. Analyser les différences par compte
    print(f"\n📈 ÉVOLUTION DES COMPTES (30j → 90j)")
    print("-" * 40)
    
    for acc in accounts_30d:
        spend_30d = accounts_30d[acc]
        spend_90d = accounts_90d.get(acc, 0)
        
        if spend_90d > 0:
            growth = ((spend_90d - spend_30d) / spend_30d * 100)
            if abs(growth) > 5:  # Changements significatifs
                symbol = "📈" if growth > 0 else "📉"
                print(f"  {symbol} {acc[:20]:20} ${spend_30d:>6,.0f} → ${spend_90d:>6,.0f} ({growth:+5.1f}%)")
    
    # 3. Analyser les méthodes de fetch
    print(f"\n🔧 ANALYSE DES MÉTHODES DE FETCH")
    print("-" * 40)
    
    print(f"30j - date_preset: {data_30d['metadata'].get('date_preset', 'N/A')}")
    print(f"90j - date_preset: {data_90d['metadata'].get('date_preset', 'N/A')}")
    print(f"30j - timestamp: {data_30d['metadata'].get('timestamp', 'N/A')[:19]}")
    print(f"90j - timestamp: {data_90d['metadata'].get('timestamp', 'N/A')[:19]}")
    
    # 4. Calculer ce qui devrait être logique
    print(f"\n🧮 CALCUL LOGIQUE ATTENDU")
    print("-" * 40)
    
    ratio_30_to_90 = 90 / 30  # 3x plus de jours
    expected_ads_90d = len(ads_30d) * ratio_30_to_90
    expected_spend_90d = sum(ad['spend'] for ad in ads_30d) * ratio_30_to_90
    
    actual_ads_90d = len(ads_90d)
    actual_spend_90d = sum(ad['spend'] for ad in ads_90d)
    
    print(f"Si croissance linéaire:")
    print(f"  Annonces attendues: {expected_ads_90d:,.0f}")
    print(f"  Spend attendu: ${expected_spend_90d:,.0f} MXN")
    print()
    print(f"Réalité:")
    print(f"  Annonces réelles: {actual_ads_90d:,.0f} ({actual_ads_90d/expected_ads_90d*100:.1f}% de l'attendu)")
    print(f"  Spend réel: ${actual_spend_90d:,.0f} MXN ({actual_spend_90d/expected_spend_90d*100:.1f}% de l'attendu)")
    
    # 5. Hypothèses
    print(f"\n🤔 HYPOTHÈSES PRINCIPALES")
    print("-" * 40)
    
    if actual_spend_90d / expected_spend_90d < 0.5:
        print("• 🎯 HYPOTHÈSE PROBABLE: Activité très récente")
        print("  → Pablo a intensifié ses campagnes dans les 30 derniers jours")
        print("  → Période 60-90 jours en arrière était calme")
    
    if missing_in_90d:
        print("• ⚠️  PROBLÈME API: Comptes manquants dans 90j")
        print(f"  → {len(missing_in_90d)} comptes perdus")
    
    if actual_ads_90d < expected_ads_90d * 0.6:
        print("• 🔧 PROBLÈME TECHNIQUE possible:")
        print("  → API last_90d ne retourne pas toutes les données")
        print("  → Recommandation: refetch avec time_range spécifique")

if __name__ == "__main__":
    investigate_discrepancy()