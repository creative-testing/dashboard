#!/usr/bin/env python3
"""
Analyse les différences entre les périodes pour comprendre pourquoi 30j et 90j sont si proches
"""
import json
from collections import defaultdict

def analyze_periods():
    periods = [7, 30, 90]
    
    print("🔍 ANALYSE DES PÉRIODES")
    print("=" * 70)
    
    for period in periods:
        filename = f"hybrid_data_{period}d.json"
        try:
            with open(filename, 'r') as f:
                data = json.load(f)
            
            ads = data['ads']
            total_spend = sum(ad['spend'] for ad in ads)
            total_impressions = sum(ad['impressions'] for ad in ads)
            
            print(f"\n📊 {period} JOURS:")
            print(f"  • Annonces: {len(ads):,}")
            print(f"  • Spend total: ${total_spend:,.0f} MXN")
            print(f"  • Impressions: {total_impressions:,}")
            print(f"  • Date preset: {data['metadata'].get('date_preset', 'N/A')}")
            
            # Analyser les comptes par spend
            account_spend = defaultdict(float)
            for ad in ads:
                account_spend[ad['account_name']] += ad['spend']
            
            top_accounts = sorted(account_spend.items(), key=lambda x: x[1], reverse=True)[:5]
            print(f"  • Top comptes:")
            for name, spend in top_accounts:
                print(f"    - {name[:25]:25}: ${spend:,.0f}")
            
            # Analyser la distribution des spends
            spend_ranges = {'0-100': 0, '100-1K': 0, '1K-10K': 0, '10K+': 0}
            for ad in ads:
                spend = ad['spend']
                if spend < 100:
                    spend_ranges['0-100'] += 1
                elif spend < 1000:
                    spend_ranges['100-1K'] += 1
                elif spend < 10000:
                    spend_ranges['1K-10K'] += 1
                else:
                    spend_ranges['10K+'] += 1
            
            print(f"  • Distribution par spend:")
            for range_name, count in spend_ranges.items():
                pct = (count / len(ads) * 100) if len(ads) > 0 else 0
                print(f"    - {range_name}: {count} ads ({pct:.1f}%)")
                
        except FileNotFoundError:
            print(f"❌ Fichier {filename} non trouvé")
    
    # Comparaison des ratios
    print(f"\n📈 RATIOS DE CROISSANCE:")
    try:
        with open('hybrid_data_7d.json') as f:
            data_7d = json.load(f)
        with open('hybrid_data_30d.json') as f:
            data_30d = json.load(f)
        with open('hybrid_data_90d.json') as f:
            data_90d = json.load(f)
        
        ads_7d, spend_7d = len(data_7d['ads']), sum(ad['spend'] for ad in data_7d['ads'])
        ads_30d, spend_30d = len(data_30d['ads']), sum(ad['spend'] for ad in data_30d['ads'])
        ads_90d, spend_90d = len(data_90d['ads']), sum(ad['spend'] for ad in data_90d['ads'])
        
        print(f"  • Annonces - 7j→30j: x{ads_30d/ads_7d:.2f}")
        print(f"  • Annonces - 30j→90j: x{ads_90d/ads_30d:.2f}")
        print(f"  • Spend - 7j→30j: x{spend_30d/spend_7d:.2f}")
        print(f"  • Spend - 30j→90j: x{spend_90d/spend_30d:.2f}")
        
        print(f"\n🤔 HYPOTHÈSES:")
        if ads_90d/ads_30d < 1.2:
            print("  • Très peu de nouvelles annonces entre 30j et 90j")
            print("  • Possible: campagnes récentes concentrées sur les 30 derniers jours")
        
        if spend_90d/spend_30d < 1.2:
            print("  • Très peu de spend supplémentaire entre 30j et 90j") 
            print("  • Possible: budgets épuisés ou saisonnalité")
            
    except Exception as e:
        print(f"❌ Erreur dans l'analyse: {e}")

if __name__ == "__main__":
    analyze_periods()