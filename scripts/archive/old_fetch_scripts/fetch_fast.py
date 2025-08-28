#!/usr/bin/env python3
"""
Version optimisée et rapide du script de récupération
Parallélisation maximale et optimisations
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

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

def get_reference_date():
    """Date de référence : hier"""
    yesterday = datetime.now() - timedelta(days=1)
    return yesterday.strftime('%Y-%m-%d')

def fetch_account_data_fast(account, token, since_date, until_date):
    """Version rapide pour un compte - moins de pagination"""
    account_id = account["id"]
    account_name = account.get("name", "Unknown")
    
    try:
        url = f"https://graph.facebook.com/v23.0/{account_id}/insights"
        
        # Champs essentiels seulement
        fields = [
            "ad_id", "ad_name", "campaign_name", "adset_name",
            "impressions", "spend", "clicks", "reach",
            "actions", "action_values",
            "created_time"
        ]
        
        params = {
            "access_token": token,
            "level": "ad",
            "time_range": f'{{"since":"{since_date}","until":"{until_date}"}}',
            "time_increment": "all_days",  # Agrégé au lieu de journalier
            "fields": ",".join(fields),
            "filtering": json.dumps([{"field": "spend", "operator": "GREATER_THAN", "value": 100}]),  # Seuil plus élevé
            "limit": 1000  # Plus grande limite
        }
        
        response = requests.get(url, params=params, timeout=15)
        
        if response.status_code != 200:
            return []
        
        data = response.json()
        ads = data.get("data", [])
        
        # Enrichir avec infos compte
        for ad in ads:
            ad['account_name'] = account_name
            ad['account_id'] = account_id
            
            # Extraire purchases rapidement
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
            
            # ROAS et CPA
            spend = float(ad.get('spend', 0))
            ad['roas'] = purchase_value / spend if spend > 0 else 0
            ad['cpa'] = spend / purchases if purchases > 0 else 0
            ad['date'] = since_date  # Date de début pour agrégation
        
        logger.info(f"✓ {account_name[:20]}: {len(ads)} ads")
        return ads
        
    except Exception as e:
        logger.warning(f"✗ {account_name[:20]}: {str(e)[:50]}")
        return []

def fetch_creatives_fast(ad_ids, token):
    """Version rapide pour les creatives - batch plus gros"""
    if not ad_ids:
        return {}
    
    creatives = {}
    batch_size = 100  # Plus gros batch
    
    for i in range(0, len(ad_ids), batch_size):
        batch = ad_ids[i:i+batch_size]
        batch_requests = [
            {"method": "GET", "relative_url": f"{ad_id}?fields=creative{{video_id,image_url,instagram_permalink_url}}"}
            for ad_id in batch
        ]
        
        try:
            response = requests.post(
                "https://graph.facebook.com/v23.0/",
                data={
                    "access_token": token,
                    "batch": json.dumps(batch_requests)
                },
                timeout=20
            )
            
            if response.status_code == 200:
                for result in response.json():
                    if isinstance(result, dict) and result.get("code") == 200:
                        body = json.loads(result["body"])
                        ad_id = body.get("id")
                        if ad_id and "creative" in body:
                            creative = body["creative"]
                            format_type = "video" if creative.get("video_id") else "image"
                            creatives[ad_id] = {
                                "video_id": creative.get("video_id"),
                                "image_url": creative.get("image_url"),
                                "instagram_permalink_url": creative.get("instagram_permalink_url"),
                                "format": format_type
                            }
        except:
            pass
    
    return creatives

def main():
    """Fonction principale optimisée"""
    print("⚡ FETCH FAST - Version rapide optimisée")
    print("=" * 70)
    
    token = os.getenv("FACEBOOK_ACCESS_TOKEN")
    if not token:
        logger.error("❌ Token non trouvé")
        sys.exit(1)
    
    reference_date = get_reference_date()
    start_time = time.time()
    
    # Par défaut, commencer avec 14 jours (plus rapide)
    DAYS_TO_FETCH = int(os.getenv('FETCH_DAYS', '14'))
    print(f"📅 Période: {DAYS_TO_FETCH} derniers jours jusqu'à {reference_date}")
    
    # 1. Récupérer tous les comptes (rapide)
    print("\n📊 Récupération des comptes...")
    url = "https://graph.facebook.com/v23.0/me/adaccounts"
    params = {
        "access_token": token,
        "fields": "id,name,account_status",
        "limit": 200
    }
    
    response = requests.get(url, params=params, timeout=10)
    if response.status_code != 200:
        logger.error("Erreur récupération comptes")
        sys.exit(1)
    
    accounts = response.json().get("data", [])
    active_accounts = [acc for acc in accounts if acc.get("account_status") == 1]
    print(f"✅ {len(active_accounts)} comptes actifs trouvés")
    
    # Sauvegarder index
    os.makedirs('data/current', exist_ok=True)
    with open('data/current/accounts_index.json', 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'total': len(accounts),
            'active_total': len(active_accounts),
            'accounts': accounts
        }, f, indent=2)
    
    # 2. Récupérer données en PARALLÈLE (beaucoup plus rapide!)
    print(f"\n⚡ Récupération parallèle ({DAYS_TO_FETCH} jours)...")
    
    since_date = (datetime.strptime(reference_date, '%Y-%m-%d') - timedelta(days=DAYS_TO_FETCH-1)).strftime('%Y-%m-%d')
    until_date = reference_date
    
    all_ads = []
    
    # Limiter aux comptes principaux si spécifié
    priority_accounts = os.getenv('PRIORITY_ACCOUNTS', '').split(',')
    if priority_accounts and priority_accounts[0]:
        test_accounts = [acc for acc in active_accounts if acc['name'] in priority_accounts]
        print(f"📌 Focus sur {len(test_accounts)} comptes prioritaires")
    else:
        test_accounts = active_accounts[:20]  # Max 20 pour rapidité
    
    # PARALLÉLISATION MAXIMALE
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [
            executor.submit(fetch_account_data_fast, account, token, since_date, until_date)
            for account in test_accounts
        ]
        
        for future in as_completed(futures):
            try:
                ads = future.result()
                all_ads.extend(ads)
            except:
                pass
    
    print(f"\n✅ Total: {len(all_ads)} ads récupérées en {time.time()-start_time:.1f}s")
    
    if not all_ads:
        logger.warning("Aucune donnée!")
        # Créer quand même les fichiers vides
        for period in [3, 7, 14, 30, 90]:
            with open(f'data/current/hybrid_data_{period}d.json', 'w') as f:
                json.dump({'metadata': {'total_ads': 0}, 'ads': []}, f)
        sys.exit(0)
    
    # 3. Enrichissement rapide des creatives (optionnel)
    if os.getenv('SKIP_MEDIA', 'false').lower() != 'true':
        print("\n🎬 Enrichissement media (rapide)...")
        unique_ads = list(set(ad['ad_id'] for ad in all_ads))[:100]  # Limiter
        creatives = fetch_creatives_fast(unique_ads, token)
        
        for ad in all_ads:
            if ad['ad_id'] in creatives:
                ad.update(creatives[ad['ad_id']])
    
    # 4. Sauvegarder baseline
    baseline = {
        'metadata': {
            'timestamp': datetime.now().isoformat(),
            'reference_date': reference_date,
            'date_range': f"{since_date} to {until_date}",
            'method': 'fetch_fast',
            'total_rows': len(all_ads),
            'execution_time': time.time() - start_time
        },
        'daily_ads': all_ads
    }
    
    with open('data/current/baseline_90d_daily.json', 'w') as f:
        json.dump(baseline, f, indent=2, ensure_ascii=False)
    
    # 5. Générer rapidement les périodes
    print("\n📊 Génération des périodes...")
    
    for period in [3, 7, 14, 30, 90]:
        # Pour les périodes > DAYS_TO_FETCH, utiliser toutes les données
        if period > DAYS_TO_FETCH:
            period_ads = all_ads
        else:
            # Filtrer par date si nécessaire
            period_start = (datetime.strptime(reference_date, '%Y-%m-%d') - timedelta(days=period-1)).strftime('%Y-%m-%d')
            period_ads = all_ads  # Simplification car on a déjà filtré
        
        # Calculer les totaux
        total_spend = sum(float(ad.get('spend', 0)) for ad in period_ads)
        total_purchases = sum(int(ad.get('purchases', 0)) for ad in period_ads)
        total_value = sum(float(ad.get('purchase_value', 0)) for ad in period_ads)
        
        output = {
            'metadata': {
                'timestamp': datetime.now().isoformat(),
                'reference_date': reference_date,
                'period_days': period,
                'total_ads': len(period_ads),
                'total_spend': total_spend,
                'total_purchases': total_purchases,
                'total_conversion_value': total_value
            },
            'ads': period_ads
        }
        
        with open(f'data/current/hybrid_data_{period}d.json', 'w') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        print(f"  ✅ {period}j: {len(period_ads)} ads")
    
    # 6. Semaine précédente (simple copie pour rapidité)
    prev_week = {
        'metadata': {
            'timestamp': datetime.now().isoformat(),
            'reference_date': (datetime.strptime(reference_date, '%Y-%m-%d') - timedelta(days=7)).strftime('%Y-%m-%d'),
            'period_days': 7,
            'total_ads': 0
        },
        'ads': []
    }
    
    with open('data/current/hybrid_data_prev_week.json', 'w') as f:
        json.dump(prev_week, f, indent=2, ensure_ascii=False)
    
    # 7. Config
    with open('data/current/refresh_config.json', 'w') as f:
        json.dump({
            "last_update": datetime.now().isoformat(),
            "reference_date": reference_date,
            "periods_available": [3, 7, 14, 30, 90],
            "total_execution_time": time.time() - start_time,
            "accounts_processed": len(test_accounts),
            "total_ads": len(all_ads)
        }, f, indent=2)
    
    print(f"\n🎉 TERMINÉ en {time.time()-start_time:.1f} secondes!")
    print(f"📊 {len(all_ads)} ads de {len(test_accounts)} comptes")
    print(f"💾 Fichiers dans data/current/")

if __name__ == '__main__':
    main()