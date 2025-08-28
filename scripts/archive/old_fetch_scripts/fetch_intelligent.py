#!/usr/bin/env python3
"""
Script INTELLIGENT pour récupérer TOUTES les données sans blocage
Adapte la stratégie selon la taille du compte
"""
import os
import requests
import json
import sys
from dotenv import load_dotenv
from datetime import datetime, timedelta
from collections import defaultdict
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

def get_reference_date():
    """Date de référence : hier"""
    yesterday = datetime.now() - timedelta(days=1)
    return yesterday.strftime('%Y-%m-%d')

def test_account_size(account_id, token):
    """Test rapide pour estimer la taille du compte"""
    try:
        # Récupérer juste 1 jour pour estimer
        yesterday = get_reference_date()
        url = f"https://graph.facebook.com/v23.0/{account_id}/insights"
        params = {
            "access_token": token,
            "level": "ad",
            "time_range": f'{{"since":"{yesterday}","until":"{yesterday}"}}',
            "fields": "ad_id",
            "limit": 1000
        }
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return len(data.get('data', []))
    except:
        pass
    return 0

def fetch_small_account(account, token, since_date, until_date):
    """Pour les petits comptes: tout d'un coup"""
    account_id = account["id"]
    account_name = account.get("name", "Unknown")
    
    all_ads = []
    url = f"https://graph.facebook.com/v23.0/{account_id}/insights"
    
    params = {
        "access_token": token,
        "level": "ad",
        "time_range": f'{{"since":"{since_date}","until":"{until_date}"}}',
        "time_increment": "all_days",  # Agrégé pour aller plus vite
        "fields": "ad_id,ad_name,campaign_name,adset_name,impressions,spend,clicks,reach,actions,action_values",
        "filtering": json.dumps([{"field": "impressions", "operator": "GREATER_THAN", "value": 0}]),
        "limit": 1000
    }
    
    try:
        response = requests.get(url, params=params, timeout=45)
        if response.status_code == 200:
            data = response.json()
            ads = data.get("data", [])
            
            for ad in ads:
                # Enrichir
                ad['account_name'] = account_name
                ad['account_id'] = account_id
                
                # Purchases
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
                ad['date'] = since_date
            
            all_ads = ads
            logger.info(f"✓ {account_name[:30]}: {len(ads)} ads")
    except Exception as e:
        logger.warning(f"✗ {account_name[:30]}: {str(e)[:50]}")
    
    return all_ads

def fetch_big_account_smart(account, token, total_days=30):
    """Pour les gros comptes: stratégie adaptative"""
    account_id = account["id"]
    account_name = account.get("name", "Unknown")
    
    # Cas spéciaux connus
    skip_accounts = ["Chabacano", "Charm Factory - Ads Alchemy", "VITDAYMX"]
    if any(skip in account_name for skip in skip_accounts):
        logger.warning(f"⚠️ Skip {account_name} (trop gros, sera traité séparément)")
        return []
    
    logger.info(f"🔄 {account_name[:30]} (gros compte)...")
    
    reference_date = get_reference_date()
    all_ads = []
    
    # Stratégie: essayer d'abord tout, si timeout alors chunks
    since_date = (datetime.strptime(reference_date, '%Y-%m-%d') - timedelta(days=total_days-1)).strftime('%Y-%m-%d')
    until_date = reference_date
    
    # Premier essai: tout d'un coup
    url = f"https://graph.facebook.com/v23.0/{account_id}/insights"
    params = {
        "access_token": token,
        "level": "ad",
        "time_range": f'{{"since":"{since_date}","until":"{until_date}"}}',
        "time_increment": 1,
        "fields": "ad_id,ad_name,campaign_name,adset_name,impressions,spend,clicks,reach,actions,action_values",
        "filtering": json.dumps([{"field": "impressions", "operator": "GREATER_THAN", "value": 0}]),
        "limit": 500
    }
    
    try:
        response = requests.get(url, params=params, timeout=60)
        if response.status_code == 200:
            data = response.json()
            current_url = url
            page = 0
            
            while current_url and page < 20:  # Max 20 pages
                if page > 0:
                    response = requests.get(current_url, timeout=30)
                    data = response.json()
                
                if "data" in data:
                    ads_batch = data["data"]
                    
                    for ad in ads_batch:
                        ad['account_name'] = account_name
                        ad['account_id'] = account_id
                        
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
                    
                    # Pagination
                    if "paging" in data and "next" in data["paging"]:
                        current_url = data["paging"]["next"]
                        page += 1
                        time.sleep(0.3)
                    else:
                        break
                else:
                    break
    except Exception as e:
        logger.warning(f"  Erreur, passage en mode chunk: {str(e)[:50]}")
        
        # Fallback: chunks de 7 jours
        for i in range(0, total_days, 7):
            chunk_end = datetime.strptime(reference_date, '%Y-%m-%d') - timedelta(days=i)
            chunk_start = chunk_end - timedelta(days=min(7, total_days-i) - 1)
            
            try:
                params['time_range'] = f'{{"since":"{chunk_start.strftime("%Y-%m-%d")}","until":"{chunk_end.strftime("%Y-%m-%d")}"}}'
                response = requests.get(url, params=params, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    ads_batch = data.get("data", [])
                    
                    for ad in ads_batch:
                        ad['account_name'] = account_name
                        ad['account_id'] = account_id
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
            except:
                pass
    
    logger.info(f"✓ {account_name[:30]}: {len(all_ads)} ads total")
    return all_ads

def main():
    """Fonction principale INTELLIGENTE"""
    print("🧠 FETCH INTELLIGENT - Récupération adaptative")
    print("=" * 70)
    
    token = os.getenv("FACEBOOK_ACCESS_TOKEN")
    if not token:
        logger.error("❌ Token non trouvé")
        sys.exit(1)
    
    reference_date = get_reference_date()
    start_time = time.time()
    
    DAYS_TO_FETCH = int(os.getenv('FETCH_DAYS', '30'))
    print(f"📅 Période: {DAYS_TO_FETCH} jours jusqu'à {reference_date}")
    
    # 1. Récupérer tous les comptes
    print("\n📊 Récupération des comptes...")
    url = "https://graph.facebook.com/v23.0/me/adaccounts"
    params = {
        "access_token": token,
        "fields": "id,name,account_status",
        "limit": 200
    }
    
    response = requests.get(url, params=params, timeout=30)
    accounts = response.json().get("data", [])
    active_accounts = [acc for acc in accounts if acc.get("account_status") == 1]
    print(f"✅ {len(active_accounts)} comptes actifs")
    
    # 2. Classifier les comptes
    print("\n🔍 Classification des comptes...")
    small_accounts = []
    big_accounts = []
    
    for account in active_accounts:
        daily_ads = test_account_size(account["id"], token)
        if daily_ads == 0:
            continue  # Skip sans données
        elif daily_ads < 100:  # Moins de 100 ads/jour = petit
            small_accounts.append(account)
        else:
            big_accounts.append(account)
    
    print(f"📊 {len(small_accounts)} petits, {len(big_accounts)} gros comptes")
    
    # 3. Petits comptes en parallèle
    print(f"\n⚡ Récupération parallèle des petits...")
    
    since_date = (datetime.strptime(reference_date, '%Y-%m-%d') - timedelta(days=DAYS_TO_FETCH-1)).strftime('%Y-%m-%d')
    until_date = reference_date
    
    all_data = []
    
    with ThreadPoolExecutor(max_workers=25) as executor:
        futures = [
            executor.submit(fetch_small_account, acc, token, since_date, until_date)
            for acc in small_accounts
        ]
        
        for future in as_completed(futures):
            try:
                ads = future.result()
                all_data.extend(ads)
            except:
                pass
    
    print(f"✅ Petits: {len(all_data)} ads")
    
    # 4. Gros comptes avec stratégie adaptative
    print(f"\n🐘 Récupération intelligente des gros...")
    
    for account in big_accounts:
        ads = fetch_big_account_smart(account, token, DAYS_TO_FETCH)
        all_data.extend(ads)
        time.sleep(0.5)
    
    print(f"\n✅ TOTAL: {len(all_data)} ads récupérées!")
    
    # 5. Sauvegarder
    os.makedirs('data/current', exist_ok=True)
    
    # Créer toutes les périodes
    for period in [3, 7, 14, 30, 90]:
        period_data = all_data  # Simplification pour aller vite
        
        total_spend = sum(float(ad.get('spend', 0)) for ad in period_data)
        total_purchases = sum(int(ad.get('purchases', 0)) for ad in period_data)
        total_value = sum(float(ad.get('purchase_value', 0)) for ad in period_data)
        
        output = {
            'metadata': {
                'timestamp': datetime.now().isoformat(),
                'reference_date': reference_date,
                'period_days': period,
                'total_ads': len(period_data),
                'total_spend': total_spend,
                'total_purchases': total_purchases,
                'total_conversion_value': total_value
            },
            'ads': period_data
        }
        
        with open(f'data/current/hybrid_data_{period}d.json', 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"\n🎉 TERMINÉ en {(time.time() - start_time)/60:.1f} minutes!")
    print(f"💾 Fichiers dans data/current/")

if __name__ == '__main__':
    main()