#!/usr/bin/env python3
"""
Script de récupération complète des données Facebook Ads
Inclut tous les champs requis par Pablo pour le Creative Testing Dashboard
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
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

def get_reference_date():
    """Date de référence : toujours hier (journée complète)"""
    yesterday = datetime.now() - timedelta(days=1)
    return yesterday.strftime('%Y-%m-%d')

def calculate_period_dates(period_days, reference_date):
    """Calcule fenêtre pour une période depuis date référence"""
    ref = datetime.strptime(reference_date, '%Y-%m-%d')
    end_date = ref
    start_date = ref - timedelta(days=period_days - 1)
    return start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')

def test_account_access(account_id, token):
    """Test si on a accès aux données d'un compte"""
    try:
        url = f"https://graph.facebook.com/v23.0/{account_id}/campaigns"
        params = {
            "access_token": token,
            "limit": 1,
            "fields": "id"
        }
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return len(data.get('data', [])) > 0
        return False
    except:
        return False

def fetch_account_insights_robust(account, token, since_date, until_date):
    """Fetch robuste avec tous les champs requis par Pablo"""
    account_id = account["id"]
    account_name = account.get("name", "Sans nom")
    
    logger.info(f"Récupération {account_name} ({account_id})")
    
    try:
        url = f"https://graph.facebook.com/v23.0/{account_id}/insights"
        
        # Tous les champs requis
        fields = [
            "ad_id", "ad_name", "campaign_name", "adset_name",
            "impressions", "spend", "clicks", "reach", "frequency",
            "ctr", "cpm", "cpp", "cpc",
            "actions", "action_values", "cost_per_action_type",
            "created_time", "updated_time"
        ]
        
        params = {
            "access_token": token,
            "level": "ad",
            "time_range": f'{{"since":"{since_date}","until":"{until_date}"}}',
            "time_increment": 1,  # Données journalières
            "fields": ",".join(fields),
            "filtering": json.dumps([{"field": "impressions", "operator": "GREATER_THAN", "value": 0}]),
            "limit": 500
        }
        
        all_ads = []
        current_url = url
        page = 0
        max_pages = 50
        backoff = 1
        
        while current_url and page < max_pages:
            try:
                if page == 0:
                    response = requests.get(current_url, params=params, timeout=30)
                else:
                    response = requests.get(current_url, timeout=30)
                
                if response.status_code != 200:
                    # Gestion du rate limiting
                    if response.status_code == 429 or '#80004' in response.text:
                        wait_time = min(30, backoff * 2)
                        logger.warning(f"Rate limit pour {account_name}, attente {wait_time}s")
                        time.sleep(wait_time)
                        backoff *= 2
                        continue
                    else:
                        logger.error(f"Erreur {response.status_code} pour {account_name}")
                        break
                
                data = response.json()
                
                if "data" in data:
                    ads_batch = data["data"]
                    
                    # Enrichir chaque ad avec les infos du compte
                    for ad in ads_batch:
                        # Infos de base
                        ad['account_name'] = account_name
                        ad['account_id'] = account_id
                        
                        # Extraire les conversions (purchases)
                        purchases = 0
                        purchase_value = 0.0
                        
                        actions = ad.get('actions', [])
                        for action in actions:
                            if action.get('action_type') in ['purchase', 'omni_purchase']:
                                purchases += int(action.get('value', 0))
                        
                        action_values = ad.get('action_values', [])
                        for value in action_values:
                            if value.get('action_type') in ['purchase', 'omni_purchase']:
                                purchase_value += float(value.get('value', 0))
                        
                        ad['purchases'] = purchases
                        ad['purchase_value'] = purchase_value
                        
                        # Calculer ROAS et CPA
                        spend = float(ad.get('spend', 0))
                        ad['roas'] = purchase_value / spend if spend > 0 else 0
                        ad['cpa'] = spend / purchases if purchases > 0 else 0
                        
                        # Date (pour les agrégations)
                        ad['date'] = ad.get('date_start', '')
                    
                    all_ads.extend(ads_batch)
                    logger.debug(f"Page {page}: {len(ads_batch)} ads récupérées")
                    
                    # Pagination
                    if "paging" in data and "next" in data["paging"]:
                        current_url = data["paging"]["next"]
                        page += 1
                        time.sleep(0.5)  # Petit délai entre les pages
                    else:
                        break
                else:
                    break
                    
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout pour {account_name}, nouvelle tentative")
                time.sleep(5)
                continue
            except Exception as e:
                logger.error(f"Erreur inattendue pour {account_name}: {str(e)}")
                break
        
        logger.info(f"✓ {account_name}: {len(all_ads)} ads récupérées")
        return all_ads
        
    except Exception as e:
        logger.error(f"Erreur finale pour {account_name}: {str(e)}")
        return []

def fetch_ad_status_and_dates(ad_ids, token):
    """Récupère le status et les dates de création pour les ads"""
    if not ad_ids:
        return {}
    
    status_info = {}
    batch_size = 50
    
    for i in range(0, len(ad_ids), batch_size):
        batch = ad_ids[i:i+batch_size]
        batch_requests = []
        
        for ad_id in batch:
            batch_requests.append({
                "method": "GET",
                "relative_url": f"{ad_id}?fields=status,effective_status,created_time,updated_time"
            })
        
        try:
            response = requests.post(
                "https://graph.facebook.com/v23.0/",
                data={
                    "access_token": token,
                    "batch": json.dumps(batch_requests)
                },
                timeout=30
            )
            
            if response.status_code == 200:
                results = response.json()
                
                for result in results:
                    if isinstance(result, dict) and result.get("code") == 200:
                        body = json.loads(result["body"])
                        ad_id = body.get("id")
                        if ad_id:
                            status_info[ad_id] = {
                                "status": body.get("status", "UNKNOWN"),
                                "effective_status": body.get("effective_status", "UNKNOWN"),
                                "created_time": body.get("created_time", ""),
                                "updated_time": body.get("updated_time", "")
                            }
        except Exception as e:
            logger.warning(f"Erreur batch status: {str(e)}")
            continue
    
    return status_info

def fetch_creatives_batch(ad_ids, token):
    """Récupère les media URLs pour un batch d'ads"""
    if not ad_ids:
        return {}
    
    creatives = {}
    batch_size = 50
    
    for i in range(0, len(ad_ids), batch_size):
        batch = ad_ids[i:i+batch_size]
        batch_requests = []
        
        for ad_id in batch:
            batch_requests.append({
                "method": "GET",
                "relative_url": f"{ad_id}?fields=creative{{video_id,image_url,instagram_permalink_url,object_story_spec}}"
            })
        
        try:
            response = requests.post(
                "https://graph.facebook.com/v23.0/",
                data={
                    "access_token": token,
                    "batch": json.dumps(batch_requests)
                },
                timeout=30
            )
            
            if response.status_code == 200:
                results = response.json()
                
                for result in results:
                    if isinstance(result, dict) and result.get("code") == 200:
                        body = json.loads(result["body"])
                        ad_id = body.get("id")
                        if ad_id and "creative" in body:
                            creative = body["creative"]
                            
                            # Déterminer le format
                            format_type = "unknown"
                            if creative.get("video_id"):
                                format_type = "video"
                            elif creative.get("image_url"):
                                format_type = "image"
                            elif creative.get("instagram_permalink_url"):
                                format_type = "instagram"
                            
                            creatives[ad_id] = {
                                "video_id": creative.get("video_id"),
                                "image_url": creative.get("image_url"),
                                "instagram_permalink_url": creative.get("instagram_permalink_url"),
                                "format": format_type
                            }
        except Exception as e:
            logger.warning(f"Erreur batch creatives: {str(e)}")
            continue
    
    return creatives

def aggregate_by_period(daily_data, period_days, reference_date):
    """Agrège les données journalières pour une période"""
    ref = datetime.strptime(reference_date, '%Y-%m-%d')
    start = ref - timedelta(days=period_days - 1)
    
    # Filtrer les données dans la période
    filtered = []
    for ad in daily_data:
        if ad.get('date'):
            try:
                ad_date = datetime.strptime(ad['date'], '%Y-%m-%d')
                if start <= ad_date <= ref:
                    filtered.append(ad)
            except:
                continue
    
    # Agréger par ad_id
    aggregated = defaultdict(lambda: {
        'impressions': 0,
        'spend': 0,
        'clicks': 0,
        'reach': 0,
        'purchases': 0,
        'purchase_value': 0,
        'dates': [],
        'daily_data': []
    })
    
    for ad in filtered:
        ad_id = ad.get('ad_id')
        if not ad_id:
            continue
            
        aggregated[ad_id]['impressions'] += int(ad.get('impressions', 0))
        aggregated[ad_id]['spend'] += float(ad.get('spend', 0))
        aggregated[ad_id]['clicks'] += int(ad.get('clicks', 0))
        aggregated[ad_id]['reach'] = max(aggregated[ad_id]['reach'], int(ad.get('reach', 0)))
        aggregated[ad_id]['purchases'] += int(ad.get('purchases', 0))
        aggregated[ad_id]['purchase_value'] += float(ad.get('purchase_value', 0))
        aggregated[ad_id]['dates'].append(ad.get('date', ''))
        aggregated[ad_id]['daily_data'].append(ad)
        
        # Conserver les infos de base (prendre la première occurrence)
        if 'ad_name' not in aggregated[ad_id]:
            aggregated[ad_id].update({
                'ad_id': ad_id,
                'ad_name': ad.get('ad_name', ''),
                'campaign_name': ad.get('campaign_name', ''),
                'adset_name': ad.get('adset_name', ''),
                'account_name': ad.get('account_name', ''),
                'account_id': ad.get('account_id', ''),
                'status': ad.get('status', 'UNKNOWN'),
                'effective_status': ad.get('effective_status', 'UNKNOWN'),
                'created_time': ad.get('created_time', ''),
                'video_id': ad.get('video_id'),
                'image_url': ad.get('image_url'),
                'instagram_permalink_url': ad.get('instagram_permalink_url'),
                'format': ad.get('format', 'unknown')
            })
    
    # Calculer les métriques dérivées
    result = []
    for ad_id, data in aggregated.items():
        spend = data['spend']
        impressions = data['impressions']
        clicks = data['clicks']
        purchases = data['purchases']
        purchase_value = data['purchase_value']
        
        # Métriques calculées
        data['ctr'] = (clicks / impressions * 100) if impressions > 0 else 0
        data['cpm'] = (spend / impressions * 1000) if impressions > 0 else 0
        data['frequency'] = impressions / data['reach'] if data['reach'] > 0 else 0
        data['roas'] = purchase_value / spend if spend > 0 else 0
        data['cpa'] = spend / purchases if purchases > 0 else 0
        data['active_days'] = len(set(data['dates']))
        
        # Nettoyer les champs temporaires
        del data['dates']
        del data['daily_data']
        
        result.append(data)
    
    return result

def main():
    """Fonction principale"""
    print("🚀 FETCH ALL DATA - Récupération complète pour Pablo")
    print("=" * 70)
    
    token = os.getenv("FACEBOOK_ACCESS_TOKEN")
    if not token:
        logger.error("❌ FACEBOOK_ACCESS_TOKEN non trouvé dans .env")
        sys.exit(1)
    
    reference_date = get_reference_date()
    print(f"📅 Date référence (hier): {reference_date}")
    print(f"🕐 Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    start_time = time.time()
    
    # 1. Récupérer tous les comptes
    print("\n📊 Récupération des comptes...")
    accounts = []
    url = "https://graph.facebook.com/v23.0/me/adaccounts"
    params = {
        "access_token": token,
        "fields": "id,name,account_status,currency,timezone_name",
        "limit": 200
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        if response.status_code == 200:
            data = response.json()
            accounts = data.get("data", [])
    except Exception as e:
        logger.error(f"Erreur récupération comptes: {str(e)}")
        sys.exit(1)
    
    # Filtrer les comptes actifs
    active_accounts = [acc for acc in accounts if acc.get("account_status") in [1, "1"]]
    print(f"✅ {len(accounts)} comptes trouvés, {len(active_accounts)} actifs")
    
    # Sauvegarder l'index des comptes
    os.makedirs('data/current', exist_ok=True)
    accounts_index = {
        'timestamp': datetime.now().isoformat(),
        'total': len(accounts),
        'active_total': len(active_accounts),
        'accounts': accounts,
        'active_accounts': active_accounts
    }
    with open('data/current/accounts_index.json', 'w', encoding='utf-8') as f:
        json.dump(accounts_index, f, indent=2, ensure_ascii=False)
    
    # 2. Tester quels comptes ont des données
    print("\n🔍 Test d'accès aux comptes...")
    accounts_with_access = []
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(test_account_access, acc["id"], token): acc for acc in active_accounts}
        
        for future in as_completed(futures):
            account = futures[future]
            try:
                has_access = future.result()
                if has_access:
                    accounts_with_access.append(account)
                    print(f"  ✓ {account['name']}")
                else:
                    print(f"  ✗ {account['name']} (pas de campagnes)")
            except Exception as e:
                print(f"  ⚠ {account['name']} (erreur)")
    
    print(f"\n✅ {len(accounts_with_access)} comptes avec données accessibles")
    
    if not accounts_with_access:
        logger.warning("Aucun compte avec données accessibles!")
        sys.exit(0)
    
    # 3. Récupérer les données pour 90 jours
    print("\n📈 Récupération des insights (90 jours)...")
    since_date, until_date = calculate_period_dates(90, reference_date)
    
    all_daily_data = []
    
    # Limiter pour les tests initiaux
    test_accounts = accounts_with_access[:10] if len(accounts_with_access) > 10 else accounts_with_access
    
    for account in test_accounts:
        ads_data = fetch_account_insights_robust(account, token, since_date, until_date)
        all_daily_data.extend(ads_data)
        time.sleep(1)  # Délai entre comptes pour éviter rate limiting
    
    print(f"\n✅ Total: {len(all_daily_data)} lignes de données journalières")
    
    if not all_daily_data:
        logger.warning("Aucune donnée récupérée!")
    else:
        # 4. Enrichir avec status et dates
        print("\n📋 Enrichissement status et dates...")
        unique_ad_ids = list(set(ad['ad_id'] for ad in all_daily_data if ad.get('ad_id')))
        status_info = fetch_ad_status_and_dates(unique_ad_ids[:100], token)  # Limiter pour tests
        
        for ad in all_daily_data:
            ad_id = ad.get('ad_id')
            if ad_id in status_info:
                ad.update(status_info[ad_id])
        
        # 5. Enrichir avec media URLs
        print("\n🎬 Enrichissement media URLs...")
        creatives_info = fetch_creatives_batch(unique_ad_ids[:100], token)  # Limiter pour tests
        
        for ad in all_daily_data:
            ad_id = ad.get('ad_id')
            if ad_id in creatives_info:
                ad.update(creatives_info[ad_id])
    
    # 6. Sauvegarder baseline 90j
    baseline = {
        'metadata': {
            'timestamp': datetime.now().isoformat(),
            'reference_date': reference_date,
            'date_range': f"{since_date} to {until_date}",
            'method': 'fetch_all_data',
            'total_rows': len(all_daily_data),
            'accounts_processed': len(test_accounts)
        },
        'daily_ads': all_daily_data
    }
    
    with open('data/current/baseline_90d_daily.json', 'w', encoding='utf-8') as f:
        json.dump(baseline, f, indent=2, ensure_ascii=False)
    
    # 7. Créer les agrégations par période
    print("\n📊 Génération des périodes...")
    periods = [3, 7, 14, 30, 90]
    
    for period in periods:
        aggregated = aggregate_by_period(all_daily_data, period, reference_date)
        
        # Calculer les totaux pour les métadonnées
        total_spend = sum(ad['spend'] for ad in aggregated)
        total_purchases = sum(ad['purchases'] for ad in aggregated)
        total_value = sum(ad['purchase_value'] for ad in aggregated)
        
        output = {
            'metadata': {
                'timestamp': datetime.now().isoformat(),
                'reference_date': reference_date,
                'period_days': period,
                'total_ads': len(aggregated),
                'total_spend': total_spend,
                'total_purchases': total_purchases,
                'total_conversion_value': total_value,
                'avg_roas': total_value / total_spend if total_spend > 0 else 0,
                'avg_cpa': total_spend / total_purchases if total_purchases > 0 else 0
            },
            'ads': aggregated
        }
        
        with open(f'data/current/hybrid_data_{period}d.json', 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        print(f"  ✅ {period}j: {len(aggregated)} ads, ${total_spend:,.0f} MXN, {total_purchases} compras")
    
    # 8. Générer la semaine précédente
    print("\n📆 Génération semaine précédente...")
    prev_ref = (datetime.strptime(reference_date, '%Y-%m-%d') - timedelta(days=7)).strftime('%Y-%m-%d')
    prev_week = aggregate_by_period(all_daily_data, 7, prev_ref)
    
    prev_output = {
        'metadata': {
            'timestamp': datetime.now().isoformat(),
            'reference_date': prev_ref,
            'period_days': 7,
            'total_ads': len(prev_week),
            'total_spend': sum(ad['spend'] for ad in prev_week),
            'total_purchases': sum(ad['purchases'] for ad in prev_week)
        },
        'ads': prev_week
    }
    
    with open('data/current/hybrid_data_prev_week.json', 'w', encoding='utf-8') as f:
        json.dump(prev_output, f, indent=2, ensure_ascii=False)
    
    # 9. Créer fichier de config
    config_output = {
        "last_update": datetime.now().isoformat(),
        "reference_date": reference_date,
        "periods_available": periods,
        "total_execution_time": time.time() - start_time,
        "accounts_processed": len(test_accounts),
        "accounts_with_data": len([acc for acc in test_accounts if any(ad['account_id'] == acc['id'] for ad in all_daily_data)]),
        "total_ads": len(all_daily_data)
    }
    
    with open('data/current/refresh_config.json', 'w', encoding='utf-8') as f:
        json.dump(config_output, f, indent=2)
    
    print(f"\n🎉 FETCH TERMINÉ avec succès!")
    print(f"⏱️  Temps total: {(time.time() - start_time)/60:.1f} minutes")
    print(f"📊 Résumé:")
    print(f"  - {len(test_accounts)} comptes traités")
    print(f"  - {len(all_daily_data)} lignes de données journalières")
    print(f"  - {len(periods)} périodes générées")
    print(f"\n💾 Fichiers créés dans data/current/")

if __name__ == '__main__':
    main()