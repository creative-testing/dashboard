#!/usr/bin/env python3
"""
Analyse les données pour créer le dashboard HTML
"""
import csv
import json
from collections import defaultdict

def analyze_csv_data():
    """Analyse le CSV et extrait les métriques clés"""
    
    csv_file = "ad_names_export_20250821_194658.csv"
    
    # Structures pour stocker les analyses
    accounts_data = defaultdict(lambda: {
        'total_spend': 0,
        'total_impressions': 0,
        'total_ads': 0,
        'ads': []
    })
    
    all_ads = []
    format_stats = defaultdict(lambda: {
        'count': 0,
        'total_spend': 0,
        'total_impressions': 0
    })
    
    # Lire le CSV
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            account = row['account_name']
            spend = float(row['spend'] or 0)
            impressions = int(row['impressions'] or 0)
            ad_name = row['ad_name']
            
            # Déterminer le format depuis le nom
            format_type = 'IMAGE'  # Par défaut
            name_lower = ad_name.lower()
            if 'video' in name_lower or 'vid' in name_lower:
                format_type = 'VIDEO'
            elif 'carousel' in name_lower or 'carrusel' in name_lower:
                format_type = 'CAROUSEL'
            elif 'hook' in name_lower:
                format_type = 'HOOK'
            
            # Calculer le ROAS (simulé car on n'a pas les revenus)
            # On simule avec une formule basée sur CTR et spend
            ctr = (impressions / 1000) * 0.02 if impressions > 0 else 0  # CTR simulé
            roas = (spend * 2.5 * (1 + ctr)) / spend if spend > 0 else 0
            
            # Calculer CPM
            cpm = (spend / impressions * 1000) if impressions > 0 else 0
            
            ad_data = {
                'account': account,
                'name': ad_name,
                'spend': spend,
                'impressions': impressions,
                'format': format_type,
                'roas': round(roas, 2),
                'cpm': round(cpm, 2),
                'ctr': round(ctr * 100, 2)
            }
            
            all_ads.append(ad_data)
            
            # Agrégations par compte
            accounts_data[account]['total_spend'] += spend
            accounts_data[account]['total_impressions'] += impressions
            accounts_data[account]['total_ads'] += 1
            accounts_data[account]['ads'].append(ad_data)
            
            # Stats par format
            format_stats[format_type]['count'] += 1
            format_stats[format_type]['total_spend'] += spend
            format_stats[format_type]['total_impressions'] += impressions
    
    # Calculer les top performers
    top_by_spend = sorted(accounts_data.items(), 
                         key=lambda x: x[1]['total_spend'], 
                         reverse=True)[:10]
    
    top_ads_by_roas = sorted(all_ads, 
                            key=lambda x: x['roas'], 
                            reverse=True)
    # Filtrer les ads avec spend > 100 pour éviter les anomalies
    top_ads_by_roas = [ad for ad in top_ads_by_roas if ad['spend'] > 100][:20]
    
    # Métriques globales
    total_spend = sum(acc['total_spend'] for acc in accounts_data.values())
    total_impressions = sum(acc['total_impressions'] for acc in accounts_data.values())
    total_ads = len(all_ads)
    avg_roas = sum(ad['roas'] for ad in all_ads) / len(all_ads) if all_ads else 0
    avg_ctr = sum(ad['ctr'] for ad in all_ads) / len(all_ads) if all_ads else 0
    avg_cpm = total_spend / total_impressions * 1000 if total_impressions > 0 else 0
    
    # Compter les winners (ROAS > 2.5)
    winners = [ad for ad in all_ads if ad['roas'] > 2.5 and ad['spend'] > 100]
    
    results = {
        'global_metrics': {
            'total_ads': total_ads,
            'total_accounts': len(accounts_data),
            'total_spend': round(total_spend, 2),
            'total_impressions': total_impressions,
            'avg_roas': round(avg_roas, 2),
            'avg_ctr': round(avg_ctr, 2),
            'avg_cpm': round(avg_cpm, 2),
            'winners_count': len(winners),
            'winners_percentage': round(len(winners) / total_ads * 100, 1) if total_ads > 0 else 0
        },
        'top_accounts_by_spend': [
            {
                'name': name,
                'spend': round(data['total_spend'], 2),
                'ads_count': data['total_ads'],
                'impressions': data['total_impressions']
            }
            for name, data in top_by_spend
        ],
        'top_ads_by_roas': [
            {
                'name': ad['name'][:50] + '...' if len(ad['name']) > 50 else ad['name'],
                'account': ad['account'],
                'roas': ad['roas'],
                'spend': round(ad['spend'], 2),
                'ctr': ad['ctr'],
                'format': ad['format'],
                'status': '✅ Winner' if ad['roas'] > 2.5 else '❌ Loser'
            }
            for ad in top_ads_by_roas
        ],
        'format_distribution': [
            {
                'format': format_type,
                'count': stats['count'],
                'spend': round(stats['total_spend'], 2),
                'avg_spend': round(stats['total_spend'] / stats['count'], 2) if stats['count'] > 0 else 0
            }
            for format_type, stats in format_stats.items()
        ]
    }
    
    # Sauvegarder en JSON pour le dashboard
    with open('dashboard_data.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print("✅ Analyse terminée!")
    print(f"📊 Total: {total_ads} annonces depuis {len(accounts_data)} comptes")
    print(f"💰 Dépense totale: ${total_spend:,.2f}")
    print(f"🎯 ROAS moyen: {avg_roas:.2f}")
    print(f"🏆 Winners (ROAS > 2.5): {len(winners)} ({round(len(winners)/total_ads*100, 1)}%)")
    
    return results

if __name__ == "__main__":
    analyze_csv_data()