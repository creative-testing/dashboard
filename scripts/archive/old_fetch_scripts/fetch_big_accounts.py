#!/usr/bin/env python3
"""
Script spécial pour les GROS comptes qui timeout
Sans limite de temps, séquentiel
"""
import os
import requests
import json
from dotenv import load_dotenv
from datetime import datetime, timedelta
import time

load_dotenv()

def fetch_big_account(account_name, account_id, token, days=30):
    """Fetch un gros compte sans timeout, avec pagination complète"""
    print(f"\n🎯 Récupération de {account_name} ({account_id})...")
    
    reference_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    since_date = (datetime.strptime(reference_date, '%Y-%m-%d') - timedelta(days=days-1)).strftime('%Y-%m-%d')
    until_date = reference_date
    
    print(f"   Période: {since_date} à {until_date}")
    
    all_ads = []
    url = f"https://graph.facebook.com/v23.0/{account_id}/insights"
    
    params = {
        "access_token": token,
        "level": "ad",
        "time_range": f'{{"since":"{since_date}","until":"{until_date}"}}',
        "time_increment": 1,
        "fields": "ad_id,ad_name,campaign_name,adset_name,impressions,spend,clicks,reach,actions,action_values,created_time",
        "filtering": json.dumps([{"field": "impressions", "operator": "GREATER_THAN", "value": 0}]),
        "limit": 500  # Plus petit pour éviter timeout
    }
    
    current_url = url
    page = 0
    max_pages = 200  # Plus de pages autorisées
    
    while current_url and page < max_pages:
        try:
            if page == 0:
                response = requests.get(current_url, params=params, timeout=60)
            else:
                response = requests.get(current_url, timeout=60)
            
            if response.status_code == 429:  # Rate limit
                print(f"   Rate limit, attente 30s...")
                time.sleep(30)
                continue
            
            if response.status_code != 200:
                print(f"   Erreur {response.status_code}")
                break
            
            data = response.json()
            
            if "data" in data:
                ads_batch = data["data"]
                
                for ad in ads_batch:
                    # Enrichir
                    ad['account_name'] = account_name
                    ad['account_id'] = account_id
                    
                    # Extraire purchases
                    purchases = 0
                    purchase_value = 0.0
                    
                    for action in ad.get('actions', []):
                        if 'purchase' in action.get('action_type', ''):
                            purchases += int(action.get('value', 0))
                    
                    for value in ad.get('action_values', []):
                        if 'purchase' in value.get('action_type', ''):
                            purchase_value += float(value.get('value', 0))
                    
                    ad['purchases'] = purchases
                    ad['purchase_value'] = purchase_value
                    
                    spend = float(ad.get('spend', 0))
                    ad['roas'] = purchase_value / spend if spend > 0 else 0
                    ad['cpa'] = spend / purchases if purchases > 0 else 0
                    ad['date'] = ad.get('date_start', '')
                
                all_ads.extend(ads_batch)
                
                # Progress
                if page % 5 == 0:
                    print(f"   Page {page}: {len(all_ads)} ads jusqu'à maintenant...")
                
                # Pagination
                if "paging" in data and "next" in data["paging"]:
                    current_url = data["paging"]["next"]
                    page += 1
                    time.sleep(0.5)  # Petit délai
                else:
                    break
            else:
                break
                
        except Exception as e:
            print(f"   Erreur page {page}: {str(e)[:100]}")
            time.sleep(5)
            continue
    
    print(f"   ✅ Total: {len(all_ads)} ads récupérées")
    return all_ads

def main():
    """Récupérer les gros comptes qui ont timeout"""
    
    token = os.getenv("FACEBOOK_ACCESS_TOKEN")
    if not token:
        print("❌ Token non trouvé")
        return
    
    # Les gros comptes qui ont timeout
    big_accounts = [
        {"name": "Petcare 2", "id": "act_297112083495970"},
        {"name": "PUBLICIDAD PERFUMARA", "id": "act_235623597993209"},
        {"name": "Dr. Mon Ecommerce", "id": "act_1070900890358939"},
        {"name": "Moscca Fine Fragrance", "id": "act_1733006760567787"},
        {"name": "217777970", "id": "act_217777970"}
    ]
    
    print("🚀 RÉCUPÉRATION DES GROS COMPTES")
    print("=" * 60)
    
    all_data = []
    
    for account in big_accounts:
        ads = fetch_big_account(account["name"], account["id"], token, days=30)
        all_data.extend(ads)
        time.sleep(2)  # Pause entre comptes
    
    # Sauvegarder
    output = {
        'metadata': {
            'timestamp': datetime.now().isoformat(),
            'accounts': len(big_accounts),
            'total_ads': len(all_data)
        },
        'ads': all_data
    }
    
    with open('data/current/big_accounts_30d.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"\n🎉 TERMINÉ!")
    print(f"📊 Total: {len(all_data)} ads des gros comptes")
    print(f"💾 Sauvegardé dans: data/current/big_accounts_30d.json")

if __name__ == '__main__':
    main()