#!/usr/bin/env python3
"""
Script pour réessayer UNIQUEMENT les comptes qui ont échoué
Cible spécifiquement: Petcare 2, KRAPEL, WU, Chabacano 1, SEPUA
"""
import os
import requests
import json
import sys
from dotenv import load_dotenv
from datetime import datetime, timedelta
import time
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

# Comptes à réessayer (basé sur les erreurs du dernier fetch)
FAILED_ACCOUNTS = [
    "Petcare 2",
    "KRAPEL CUENTA PUBLICITARIA", 
    "WU",
    "Chabacano 1",
    "SEPUA",
    "RAW APHOTECARY 2"  # Aussi 0 ads
]

def fetch_account_with_retry(account, token, since_date, until_date, max_retries=5):
    """Récupération avec plusieurs tentatives et différentes stratégies"""
    account_id = account["id"]
    account_name = account.get("name", "Unknown")
    
    strategies = [
        {"limit": 500, "delay": 0},     # Tentative normale
        {"limit": 250, "delay": 5},     # Limite réduite
        {"limit": 100, "delay": 10},    # Limite très réduite
        {"limit": 50, "delay": 15},     # Petits batchs
        {"limit": 25, "delay": 20},     # Très petits batchs
    ]
    
    for attempt, strategy in enumerate(strategies):
        logger.info(f"\n🔄 Tentative {attempt+1}/{len(strategies)} pour {account_name} (limit={strategy['limit']})")
        
        if strategy['delay'] > 0:
            logger.info(f"  ⏳ Attente de {strategy['delay']}s...")
            time.sleep(strategy['delay'])
        
        all_ads = []
        
        try:
            url = f"https://graph.facebook.com/v23.0/{account_id}/insights"
            
            params = {
                "access_token": token,
                "level": "ad",
                "time_range": f'{{"since":"{since_date}","until":"{until_date}"}}',
                "time_increment": 1,
                "fields": "ad_id,ad_name,campaign_name,campaign_id,adset_name,adset_id,impressions,spend,clicks,reach,frequency,actions,action_values,created_time",
                "filtering": json.dumps([{"field": "impressions", "operator": "GREATER_THAN", "value": 0}]),
                "limit": strategy['limit']
            }
            
            current_url = url
            page = 0
            max_pages = 200  # Plus de pages permises
            
            while current_url and page < max_pages:
                if page == 0:
                    response = requests.get(current_url, params=params, timeout=180)
                else:
                    response = requests.get(current_url, timeout=180)
                
                logger.info(f"  Page {page+1}: Status {response.status_code}")
                
                if response.status_code == 429:
                    logger.info(f"  Rate limit, attente 60s...")
                    time.sleep(60)
                    continue
                
                if response.status_code == 500:
                    logger.warning(f"  Erreur serveur, nouvelle tentative...")
                    time.sleep(30)
                    break  # On passe à la stratégie suivante
                
                if response.status_code == 400:
                    logger.warning(f"  Erreur 400 - Détails: {response.text[:200]}")
                    break  # On passe à la stratégie suivante
                
                if response.status_code != 200:
                    logger.warning(f"  Erreur {response.status_code}")
                    break
                
                data = response.json()
                
                if "data" in data:
                    ads_batch = data["data"]
                    
                    for ad in ads_batch:
                        ad['account_name'] = account_name
                        ad['account_id'] = account_id
                        
                        # Extraire purchases
                        PURCHASE_KEYS = [
                            'omni_purchase',
                            'purchase',
                            'offsite_conversion.fb_pixel_purchase',
                            'onsite_web_purchase',
                        ]
                        
                        def _first_present_value(items, keys):
                            mapping = {i.get('action_type', ''): i.get('value', 0) for i in (items or [])}
                            for k in keys:
                                if k in mapping:
                                    try:
                                        return float(mapping[k] or 0)
                                    except:
                                        return 0.0
                            return 0.0
                        
                        purchases = int(_first_present_value(ad.get('actions', []), PURCHASE_KEYS))
                        purchase_value = float(_first_present_value(ad.get('action_values', []), PURCHASE_KEYS))
                        
                        ad['purchases'] = purchases
                        ad['purchase_value'] = purchase_value
                        
                        spend = float(ad.get('spend', 0))
                        ad['roas'] = purchase_value / spend if spend > 0 else 0
                        ad['cpa'] = spend / purchases if purchases > 0 else 0
                        ad['date'] = ad.get('date_start', '')
                    
                    all_ads.extend(ads_batch)
                    
                    if len(ads_batch) > 0:
                        logger.info(f"  ✓ {len(ads_batch)} ads récupérées (total: {len(all_ads)})")
                    
                    # Pagination
                    if "paging" in data and "next" in data["paging"]:
                        current_url = data["paging"]["next"]
                        page += 1
                        time.sleep(1)  # Délai entre pages
                    else:
                        break
                else:
                    logger.warning(f"  Pas de données dans la réponse")
                    break
            
            if all_ads:
                logger.info(f"✅ SUCCÈS pour {account_name}: {len(all_ads)} ads récupérées!")
                return all_ads
                
        except requests.exceptions.Timeout:
            logger.warning(f"⏱️ Timeout pour {account_name}")
        except Exception as e:
            logger.error(f"❌ Erreur pour {account_name}: {str(e)}")
    
    logger.error(f"❌ ÉCHEC DÉFINITIF pour {account_name} après {len(strategies)} tentatives")
    return []

def main():
    """Réessayer uniquement les comptes qui ont échoué"""
    print("🔄 RETRY DES COMPTES ÉCHOUÉS")
    print("=" * 70)
    
    token = os.getenv("FACEBOOK_ACCESS_TOKEN")
    if not token:
        logger.error("❌ Token non trouvé")
        sys.exit(1)
    
    # Récupérer la liste complète des comptes
    print("\n📊 Récupération des comptes...")
    url = "https://graph.facebook.com/v23.0/me/adaccounts"
    params = {
        "access_token": token,
        "fields": "id,name,account_status",
        "limit": 200
    }
    
    response = requests.get(url, params=params, timeout=30)
    if response.status_code != 200:
        logger.error(f"Erreur récupération comptes: {response.status_code}")
        sys.exit(1)
    
    all_accounts = response.json().get("data", [])
    
    # Filtrer pour avoir seulement les comptes qui ont échoué
    failed_accounts = []
    for acc in all_accounts:
        if acc.get("name") in FAILED_ACCOUNTS and acc.get("account_status") == 1:
            failed_accounts.append(acc)
            print(f"  ✓ Trouvé: {acc.get('name')}")
    
    print(f"\n📋 {len(failed_accounts)} comptes à réessayer sur {len(FAILED_ACCOUNTS)} recherchés")
    
    if not failed_accounts:
        print("❌ Aucun compte échoué trouvé")
        return
    
    # Dates (90 jours comme le fetch original)
    reference_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    since_date = (datetime.strptime(reference_date, '%Y-%m-%d') - timedelta(days=89)).strftime('%Y-%m-%d')
    until_date = reference_date
    
    print(f"\n📅 Période: {since_date} à {until_date}")
    
    # Réessayer chaque compte un par un
    all_recovered_ads = []
    
    for account in failed_accounts:
        ads = fetch_account_with_retry(account, token, since_date, until_date)
        if ads:
            all_recovered_ads.extend(ads)
            print(f"  ✅ {account.get('name')}: {len(ads)} ads récupérées")
        else:
            print(f"  ❌ {account.get('name')}: Échec définitif")
    
    # Sauvegarder les données récupérées
    if all_recovered_ads:
        print(f"\n✅ Total récupéré: {len(all_recovered_ads)} ads")
        
        # Charger les données existantes
        existing_file = 'data/current/baseline_90d_daily.json'
        if os.path.exists(existing_file):
            with open(existing_file, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
            
            # Ajouter les nouvelles données
            existing_ads = existing_data.get('daily_ads', [])
            
            # Créer un index des ads existantes pour éviter les doublons
            existing_ad_ids = {(ad['ad_id'], ad['date']) for ad in existing_ads}
            
            # Ajouter seulement les nouvelles ads
            new_ads_added = 0
            for ad in all_recovered_ads:
                if (ad['ad_id'], ad['date']) not in existing_ad_ids:
                    existing_ads.append(ad)
                    new_ads_added += 1
            
            existing_data['daily_ads'] = existing_ads
            existing_data['metadata']['total_rows'] = len(existing_ads)
            existing_data['metadata']['last_retry'] = datetime.now().isoformat()
            existing_data['metadata']['retry_recovered'] = new_ads_added
            
            # Sauvegarder
            with open(existing_file, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, indent=2, ensure_ascii=False)
            
            print(f"✅ {new_ads_added} nouvelles ads ajoutées au fichier existant")
            print(f"📊 Total dans le fichier: {len(existing_ads)} ads")
            
            # Regénérer les périodes
            print("\n🔄 Regénération des périodes...")
            os.system("python scripts/production/compress_after_fetch.py --input-dir data/current")
        else:
            # Sauvegarder dans un nouveau fichier
            output_file = 'data/current/retry_recovered_ads.json'
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'metadata': {
                        'timestamp': datetime.now().isoformat(),
                        'reference_date': reference_date,
                        'accounts_recovered': [acc.get('name') for acc in failed_accounts if any(ad['account_name'] == acc.get('name') for ad in all_recovered_ads)]
                    },
                    'ads': all_recovered_ads
                }, f, indent=2, ensure_ascii=False)
            
            print(f"💾 Données sauvegardées dans {output_file}")
    else:
        print("\n❌ Aucune donnée récupérée")

if __name__ == '__main__':
    main()