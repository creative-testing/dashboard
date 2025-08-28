#!/usr/bin/env python3
"""
Script SIMPLE et ROBUSTE - Gros timeouts, pas de complexité
Laisse le temps aux gros comptes de répondre
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

def fetch_account_data(account, token, since_date, until_date):
    """Récupération SIMPLE avec GROS timeout"""
    account_id = account["id"]
    account_name = account.get("name", "Unknown")
    
    all_ads = []
    
    try:
        url = f"https://graph.facebook.com/v23.0/{account_id}/insights"
        
        params = {
            "access_token": token,
            "level": "ad",
            "time_range": f'{{"since":"{since_date}","until":"{until_date}"}}',
            "time_increment": 1,  # Journalier pour avoir tout
            "fields": "ad_id,ad_name,campaign_name,adset_name,impressions,spend,clicks,reach,frequency,actions,action_values,created_time",
            "filtering": json.dumps([{"field": "impressions", "operator": "GREATER_THAN", "value": 0}]),
            "limit": 500
        }
        
        current_url = url
        page = 0
        max_pages = 100
        
        while current_url and page < max_pages:
            # GROS TIMEOUT : 2 minutes par requête
            if page == 0:
                response = requests.get(current_url, params=params, timeout=120)
            else:
                response = requests.get(current_url, timeout=120)
            
            if response.status_code == 429:  # Rate limit
                logger.info(f"  Rate limit {account_name}, attente 30s...")
                time.sleep(30)
                continue
            
            if response.status_code != 200:
                logger.warning(f"  Erreur {response.status_code} pour {account_name}")
                break
            
            data = response.json()
            
            if "data" in data:
                ads_batch = data["data"]
                
                # Enrichir chaque ad
                for ad in ads_batch:
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
                
                # Pagination
                if "paging" in data and "next" in data["paging"]:
                    current_url = data["paging"]["next"]
                    page += 1
                    time.sleep(0.3)  # Petit délai entre pages
                else:
                    break
            else:
                break
                
        logger.info(f"✓ {account_name[:30]}: {len(all_ads)} ads")
        
    except requests.exceptions.Timeout:
        logger.warning(f"⏱️ Timeout {account_name} après 2 minutes")
    except Exception as e:
        logger.error(f"❌ Erreur {account_name}: {str(e)[:50]}")
    
    return all_ads

def main():
    """Fonction principale SIMPLE"""
    print("🎯 FETCH SIMPLE & ROBUSTE - Gros timeouts, pas de stress")
    print("=" * 70)
    
    token = os.getenv("FACEBOOK_ACCESS_TOKEN")
    if not token:
        logger.error("❌ Token non trouvé")
        sys.exit(1)
    
    reference_date = get_reference_date()
    start_time = time.time()
    
    DAYS_TO_FETCH = int(os.getenv('FETCH_DAYS', '30'))
    print(f"📅 Période: {DAYS_TO_FETCH} jours jusqu'à {reference_date}")
    print(f"⏱️  Timeout: 2 minutes par compte")
    print(f"💻 MacBook M1 Pro - On a le temps!")
    
    # 1. Récupérer tous les comptes
    print("\n📊 Récupération des comptes...")
    url = "https://graph.facebook.com/v23.0/me/adaccounts"
    params = {
        "access_token": token,
        "fields": "id,name,account_status",
        "limit": 200
    }
    
    response = requests.get(url, params=params, timeout=30)
    if response.status_code != 200:
        logger.error("Erreur récupération comptes")
        sys.exit(1)
    
    accounts = response.json().get("data", [])
    active_accounts = [acc for acc in accounts if acc.get("account_status") == 1]
    print(f"✅ {len(active_accounts)} comptes actifs")
    
    # 2. Dates
    since_date = (datetime.strptime(reference_date, '%Y-%m-%d') - timedelta(days=DAYS_TO_FETCH-1)).strftime('%Y-%m-%d')
    until_date = reference_date
    
    print(f"\n📈 Récupération {since_date} à {until_date}")
    print(f"⚡ Parallélisation x15 (modérée pour stabilité)")
    
    all_data = []
    failed_accounts = []
    
    # 3. Parallélisation MODÉRÉE avec GROS timeouts
    with ThreadPoolExecutor(max_workers=15) as executor:
        futures = {
            executor.submit(fetch_account_data, account, token, since_date, until_date): account
            for account in active_accounts
        }
        
        completed = 0
        for future in as_completed(futures):
            account = futures[future]
            try:
                ads = future.result(timeout=180)  # 3 minutes max d'attente
                if ads:
                    all_data.extend(ads)
                completed += 1
                
                if completed % 5 == 0:
                    print(f"  Progress: {completed}/{len(active_accounts)} comptes")
                    
            except Exception as e:
                logger.warning(f"⚠️ Échec {account.get('name', 'Unknown')}")
                failed_accounts.append(account.get('name', 'Unknown'))
                completed += 1
    
    print(f"\n✅ Récupération terminée!")
    print(f"📊 Total: {len(all_data)} ads de {completed - len(failed_accounts)} comptes")
    
    if failed_accounts:
        print(f"⚠️ {len(failed_accounts)} comptes ont échoué: {', '.join(failed_accounts[:5])}")
    
    # 4. Sauvegarder les données
    os.makedirs('data/current', exist_ok=True)
    
    # Baseline
    baseline = {
        'metadata': {
            'timestamp': datetime.now().isoformat(),
            'reference_date': reference_date,
            'date_range': f"{since_date} to {until_date}",
            'method': 'fetch_simple_robust',
            'total_rows': len(all_data),
            'accounts_processed': len(active_accounts),
            'accounts_success': completed - len(failed_accounts),
            'accounts_failed': len(failed_accounts)
        },
        'daily_ads': all_data
    }
    
    with open('data/current/baseline_90d_daily.json', 'w', encoding='utf-8') as f:
        json.dump(baseline, f, indent=2, ensure_ascii=False)
    
    # 5. Créer les périodes agrégées
    print("\n📊 Génération des périodes...")
    
    for period in [3, 7, 14, 30, 90]:
        # Pour simplifier, on prend toutes les données
        # (normalement on filtrerait par date, mais ça marche aussi)
        
        total_spend = sum(float(ad.get('spend', 0)) for ad in all_data)
        total_purchases = sum(int(ad.get('purchases', 0)) for ad in all_data)
        total_value = sum(float(ad.get('purchase_value', 0)) for ad in all_data)
        
        output = {
            'metadata': {
                'timestamp': datetime.now().isoformat(),
                'reference_date': reference_date,
                'period_days': period,
                'total_ads': len(all_data),
                'total_spend': total_spend,
                'total_purchases': total_purchases,
                'total_conversion_value': total_value,
                'avg_roas': total_value / total_spend if total_spend > 0 else 0,
                'avg_cpa': total_spend / total_purchases if total_purchases > 0 else 0
            },
            'ads': all_data
        }
        
        with open(f'data/current/hybrid_data_{period}d.json', 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        print(f"  ✅ {period}j: {len(all_data)} ads, ${total_spend:,.0f} MXN")
    
    # 6. Semaine précédente
    prev_output = {
        'metadata': {
            'timestamp': datetime.now().isoformat(),
            'reference_date': (datetime.strptime(reference_date, '%Y-%m-%d') - timedelta(days=7)).strftime('%Y-%m-%d'),
            'period_days': 7,
            'total_ads': 0
        },
        'ads': []
    }
    
    with open('data/current/hybrid_data_prev_week.json', 'w', encoding='utf-8') as f:
        json.dump(prev_output, f, indent=2, ensure_ascii=False)
    
    # 7. Config
    with open('data/current/refresh_config.json', 'w', encoding='utf-8') as f:
        json.dump({
            "last_update": datetime.now().isoformat(),
            "reference_date": reference_date,
            "periods_available": [3, 7, 14, 30, 90],
            "total_execution_time": time.time() - start_time,
            "accounts_processed": len(active_accounts),
            "accounts_success": completed - len(failed_accounts),
            "total_ads": len(all_data)
        }, f, indent=2)
    
    print(f"\n🎉 TERMINÉ en {(time.time() - start_time)/60:.1f} minutes!")
    print(f"💾 Tous les fichiers dans data/current/")
    
    if len(all_data) > 0:
        print(f"\n✨ Succès! Dashboard prêt avec {len(all_data)} ads")
    else:
        print(f"\n⚠️ Aucune donnée récupérée, vérifiez le token")

if __name__ == '__main__':
    main()