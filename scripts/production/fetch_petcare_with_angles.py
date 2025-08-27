#!/usr/bin/env python3
"""
Fetch Petcare avec parsing de la nomenclature pour débloquer analyses réelles
"""
import os
import sys
import requests
import json
from dotenv import load_dotenv
from datetime import datetime
from collections import defaultdict

# Importer le parser
sys.path.append('scripts/utils')
from parse_nomenclature import parse_martin_nomenclature

load_dotenv()

def fetch_petcare_with_parsing():
    """Fetch Petcare avec parsing des angles pour vraies analyses"""
    
    token = os.getenv("FACEBOOK_ACCESS_TOKEN")
    if not token:
        raise SystemExit("FACEBOOK_ACCESS_TOKEN not set. Define it in .env")
    
    print("🚀 FETCH PETCARE AVEC PARSING D'ANGLES")
    print("=" * 60)
    print("🎯 Objectif: Débloquer analyses réelles par angle")
    
    # Trouver Petcare
    accounts_url = "https://graph.facebook.com/v23.0/me/adaccounts"
    response = requests.get(accounts_url, params={
        "access_token": token,
        "fields": "id,name,account_status",
        "limit": 100
    })
    
    accounts = response.json().get("data", [])
    petcare_account = None
    
    for acc in accounts:
        if "petcare" in acc.get("name", "").lower():
            petcare_account = acc
            break
    
    if not petcare_account:
        print("❌ Compte Petcare non trouvé")
        return None
    
    account_id = petcare_account["id"]
    account_name = petcare_account["name"]
    
    print(f"✅ Compte trouvé: {account_name} ({account_id})")
    
    # Récupérer les insights Petcare (7 derniers jours)
    print(f"\n📊 Récupération insights Petcare...")
    
    insights_url = f"https://graph.facebook.com/v23.0/{account_id}/insights"
    insights_params = {
        "access_token": token,
        "level": "ad",
        "date_preset": "last_7d",
        "fields": "ad_id,ad_name,campaign_name,adset_name,impressions,spend,clicks,ctr,cpm,reach,frequency,actions,action_values,cost_per_action_type",
        "filtering": '[{"field":"impressions","operator":"GREATER_THAN","value":"0"}]',
        "limit": 500
    }
    
    response = requests.get(insights_url, params=insights_params)
    insights_data = response.json()
    
    if "error" in insights_data:
        print(f"❌ Erreur insights: {insights_data['error']}")
        return None
    
    insights = insights_data.get("data", [])
    print(f"✅ {len(insights)} annonces avec insights")
    
    # Parser chaque annonce
    print(f"\n🧠 PARSING DES ANGLES...")
    
    angle_stats = defaultdict(lambda: {
        'ads': [],
        'total_spend': 0,
        'total_revenue': 0,
        'total_impressions': 0,
        'total_clicks': 0
    })
    
    type_stats = defaultdict(lambda: {
        'ads': [],
        'total_spend': 0,
        'total_revenue': 0
    })
    
    parsed_ads = []
    parsing_success = 0
    
    for insight in insights:
        ad_name = insight.get("ad_name", "")
        
        # Parser la nomenclature
        parsed = parse_martin_nomenclature(ad_name)
        
        if parsed['is_nomenclature']:
            parsing_success += 1
        
        # Extraire métriques
        spend = float(insight.get("spend", 0))
        impressions = int(insight.get("impressions", 0))
        clicks = int(insight.get("clicks", 0))
        ctr = float(insight.get("ctr", 0))
        cpm = float(insight.get("cpm", 0))
        
        # CPA
        cpa = 0
        cost_per_actions = insight.get("cost_per_action_type", [])
        for cpa_item in cost_per_actions:
            if cpa_item.get("action_type") in ["purchase", "omni_purchase"]:
                cpa = float(cpa_item.get("value", 0))
                break
        
        # Conversions
        purchases = 0
        purchase_value = 0
        actions = insight.get("actions", [])
        action_values = insight.get("action_values", [])
        
        for action in actions:
            if action.get("action_type") in ["purchase", "omni_purchase"]:
                purchases = int(action.get("value", 0))
                break
        
        for action_value in action_values:
            if action_value.get("action_type") in ["purchase", "omni_purchase"]:
                purchase_value = float(action_value.get("value", 0))
                break
        
        roas = (purchase_value / spend) if spend > 0 else 0
        
        # Ajouter aux stats par angle
        angle = parsed['angle']
        type_creative = parsed['type']
        
        ad_data = {
            **insight,
            **parsed,
            'spend': spend,
            'impressions': impressions,
            'clicks': clicks,
            'ctr': ctr,
            'cpm': cpm,
            'cpa': cpa,
            'purchases': purchases,
            'purchase_value': purchase_value,
            'roas': roas
        }
        
        parsed_ads.append(ad_data)
        
        # Agréger par angle
        if parsed['is_nomenclature'] and spend > 0:
            angle_stats[angle]['ads'].append(ad_data)
            angle_stats[angle]['total_spend'] += spend
            angle_stats[angle]['total_revenue'] += purchase_value
            angle_stats[angle]['total_impressions'] += impressions
            angle_stats[angle]['total_clicks'] += clicks
            
            # Agréger par type
            type_stats[type_creative]['ads'].append(ad_data)
            type_stats[type_creative]['total_spend'] += spend
            type_stats[type_creative]['total_revenue'] += purchase_value
    
    # Calculer ROAS par angle
    print(f"\n📊 ANALYSE PAR ANGLE (VRAIES DONNÉES):")
    print("-" * 40)
    
    angle_performance = []
    for angle, stats in angle_stats.items():
        if angle != 'UNKNOWN' and stats['total_spend'] > 0:
            roas = stats['total_revenue'] / stats['total_spend']
            ctr = (stats['total_clicks'] / stats['total_impressions'] * 100) if stats['total_impressions'] > 0 else 0
            
            angle_performance.append({
                'angle': angle,
                'ads_count': len(stats['ads']),
                'spend': stats['total_spend'],
                'roas': roas,
                'ctr': ctr
            })
            
            print(f"  📈 {angle:25} : {len(stats['ads']):2} ads, ${stats['total_spend']:>6,.0f}, ROAS {roas:.2f}")
    
    # Analyser par type
    print(f"\n🔄 ANALYSE PAR TYPE:")
    print("-" * 40)
    
    for type_name, stats in type_stats.items():
        if type_name != 'UNKNOWN' and stats['total_spend'] > 0:
            roas = stats['total_revenue'] / stats['total_spend']
            print(f"  🎯 {type_name:15} : {len(stats['ads']):2} ads, ${stats['total_spend']:>6,.0f}, ROAS {roas:.2f}")
    
    # Résumé
    print(f"\n" + "=" * 60)
    print(f"✅ PARSING RÉUSSI:")
    print(f"  • {parsing_success}/{len(insights)} annonces avec nomenclature ({parsing_success/len(insights)*100:.1f}%)")
    print(f"  • {len(angle_stats)} angles différents détectés")
    print(f"  • {len(type_stats)} types créatifs")
    
    # Sauvegarder pour le dashboard
    output = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "account": account_name,
            "parsing_success_rate": parsing_success/len(insights)*100 if insights else 0,
            "total_ads": len(insights)
        },
        "angle_performance": sorted(angle_performance, key=lambda x: x['roas'], reverse=True),
        "type_performance": [
            {
                'type': type_name,
                'ads_count': len(stats['ads']),
                'spend': stats['total_spend'],
                'roas': stats['total_revenue'] / stats['total_spend'] if stats['total_spend'] > 0 else 0
            }
            for type_name, stats in type_stats.items() 
            if type_name != 'UNKNOWN' and stats['total_spend'] > 0
        ],
        "parsed_ads": parsed_ads
    }
    
    filename = "data/current/petcare_parsed_analysis.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Données sauvegardées: {filename}")
    print(f"🎉 PRÊT POUR DÉBLOQUER LES ANALYSES AVANCÉES !")
    
    return output

if __name__ == "__main__":
    print("🧠 Fetch Petcare avec parsing d'angles")
    print("🎯 Martin a mis la nomenclature → on peut analyser !")
    
    result = fetch_petcare_with_parsing()
    
    if result:
        print("\n✨ Succès ! Analyses réelles par angle disponibles !")
