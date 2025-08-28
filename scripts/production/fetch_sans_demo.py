#!/usr/bin/env python3
"""
Script ROBUSTE SANS démographies - Récupère TOUT sauf age/gender
Combine insights + creatives + media URLs
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

def fetch_account_insights(account, token, since_date, until_date):
    """Récupération des MÉTRIQUES (sans démographies)"""
    account_id = account["id"]
    account_name = account.get("name", "Unknown")
    
    all_ads = []
    
    try:
        url = f"https://graph.facebook.com/v23.0/{account_id}/insights"
        
        params = {
            "access_token": token,
            "level": "ad",
            "time_range": f'{{"since":"{since_date}","until":"{until_date}"}}',
            "time_increment": 1,  # Journalier
            "fields": "ad_id,ad_name,campaign_name,campaign_id,adset_name,adset_id,impressions,spend,clicks,reach,frequency,actions,action_values,created_time",
            "filtering": json.dumps([{"field": "impressions", "operator": "GREATER_THAN", "value": 0}]),
            "limit": 500
        }
        
        current_url = url
        page = 0
        max_pages = 100
        
        while current_url and page < max_pages:
            # Timeout raisonnable
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
                    time.sleep(0.3)
                else:
                    break
            else:
                break
                
        logger.info(f"✓ {account_name[:30]}: {len(all_ads)} ads (métriques)")
        
    except requests.exceptions.Timeout:
        logger.warning(f"⏱️ Timeout {account_name}")
    except Exception as e:
        logger.error(f"❌ Erreur {account_name}: {str(e)[:50]}")
    
    return all_ads

def fetch_creatives_batch(ad_ids, token):
    """Récupérer les CREATIVES (status, format, media) par batch"""
    if not ad_ids:
        return {}
    
    # Préparer les requêtes batch
    batch_requests = []
    for ad_id in ad_ids[:50]:  # Max 50 par batch
        batch_requests.append({
            "method": "GET",
            "relative_url": f"{ad_id}?fields=status,effective_status,created_time,creative{{status,video_id,image_url,instagram_permalink_url,object_story_spec}}"
        })
    
    try:
        url = "https://graph.facebook.com/v23.0"
        params = {
            "access_token": token,
            "batch": json.dumps(batch_requests)
        }
        
        response = requests.post(url, data=params, timeout=60)
        
        if response.status_code != 200:
            logger.warning(f"Erreur batch creatives: {response.status_code}")
            return {}
        
        results = {}
        batch_responses = response.json()
        
        for i, resp in enumerate(batch_responses):
            if resp.get("code") == 200:
                ad_data = json.loads(resp["body"])
                ad_id = ad_ids[i]
                
                # Extraire les infos
                creative = ad_data.get("creative", {})
                
                # Déterminer format et media_url
                format_type = "UNKNOWN"
                media_url = ""
                
                if creative.get("video_id"):
                    format_type = "VIDEO"
                    media_url = f"https://www.facebook.com/watch/?v={creative['video_id']}"
                elif creative.get("image_url"):
                    format_type = "IMAGE"
                    media_url = creative["image_url"]
                elif creative.get("instagram_permalink_url"):
                    format_type = "CAROUSEL"  # Souvent c'est un carousel sur Instagram
                    media_url = creative["instagram_permalink_url"]
                elif creative.get("object_story_spec"):
                    # Chercher dans object_story_spec
                    story = creative.get("object_story_spec", {})
                    if story.get("video_data"):
                        format_type = "VIDEO"
                    elif story.get("link_data", {}).get("image_hash"):
                        format_type = "IMAGE"
                
                results[ad_id] = {
                    "status": ad_data.get("status", "UNKNOWN"),
                    "effective_status": ad_data.get("effective_status", "UNKNOWN"),
                    "format": format_type,
                    "media_url": media_url,
                    "creative_status": creative.get("status", "UNKNOWN")
                }
        
        return results
        
    except Exception as e:
        logger.error(f"Erreur batch creatives: {str(e)[:50]}")
        return {}

def enrich_ads_with_creatives(ads, token):
    """Enrichir les ads avec leurs creatives"""
    logger.info(f"🎨 Enrichissement de {len(ads)} ads avec creatives...")
    logger.info(f"   Batchs de 50 ads, 25 workers en parallèle")
    
    # Grouper les ads par batch de 50
    ad_ids = [ad['ad_id'] for ad in ads]
    enriched = 0
    total_batches = (len(ad_ids) + 49) // 50
    logger.info(f"   {total_batches} batchs à traiter")
    
    with ThreadPoolExecutor(max_workers=25) as executor:
        futures = []
        for i in range(0, len(ad_ids), 50):
            batch = ad_ids[i:i+50]
            futures.append(executor.submit(fetch_creatives_batch, batch, token))
        
        creative_data = {}
        completed_batches = 0
        for future in as_completed(futures):
            try:
                batch_result = future.result(timeout=60)
                creative_data.update(batch_result)
                completed_batches += 1
                if completed_batches % 100 == 0:
                    logger.info(f"   Progress: {completed_batches}/{total_batches} batchs")
            except Exception as e:
                logger.warning(f"Erreur batch creative: {str(e)[:30]}")
                completed_batches += 1
    
    # Enrichir les ads
    for ad in ads:
        ad_id = ad['ad_id']
        if ad_id in creative_data:
            ad.update(creative_data[ad_id])
            enriched += 1
        else:
            # Valeurs par défaut
            ad['status'] = 'UNKNOWN'
            ad['effective_status'] = 'UNKNOWN'
            ad['format'] = 'UNKNOWN'
            ad['media_url'] = ''
            ad['creative_status'] = 'UNKNOWN'
    
    logger.info(f"✅ {enriched}/{len(ads)} ads enrichies avec creatives")
    return ads

def main():
    """Fonction principale SANS démographies"""
    print("🎯 FETCH SANS DÉMOGRAPHIES - Tout sauf age/gender")
    print("=" * 70)
    
    token = os.getenv("FACEBOOK_ACCESS_TOKEN")
    if not token:
        logger.error("❌ Token non trouvé")
        sys.exit(1)
    
    reference_date = get_reference_date()
    start_time = time.time()
    
    DAYS_TO_FETCH = int(os.getenv('FETCH_DAYS', '90'))
    print(f"📅 Période: {DAYS_TO_FETCH} jours jusqu'à {reference_date}")
    print(f"⚡ Workers: 32 en parallèle")
    print(f"🎨 Avec creatives (status, format, media)")
    
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
    
    print(f"\n📈 Étape 1: Récupération des métriques {since_date} à {until_date}")
    
    all_data = []
    failed_accounts = []
    
    # 3. Récupération des MÉTRIQUES en parallèle
    with ThreadPoolExecutor(max_workers=32) as executor:
        futures = {
            executor.submit(fetch_account_insights, account, token, since_date, until_date): account
            for account in active_accounts
        }
        
        completed = 0
        for future in as_completed(futures):
            account = futures[future]
            try:
                ads = future.result(timeout=180)
                if ads:
                    all_data.extend(ads)
                completed += 1
                
                if completed % 10 == 0:
                    print(f"  Progress: {completed}/{len(active_accounts)} comptes")
                    
            except Exception as e:
                logger.warning(f"⚠️ Échec {account.get('name', 'Unknown')}")
                failed_accounts.append(account.get('name', 'Unknown'))
                completed += 1
    
    print(f"\n✅ Métriques récupérées: {len(all_data)} ads")
    
    # SAUVEGARDER IMMÉDIATEMENT les métriques
    if all_data:
        os.makedirs('data/temp', exist_ok=True)
        with open('data/temp/metrics_backup.json', 'w', encoding='utf-8') as f:
            json.dump(all_data, f, indent=2, ensure_ascii=False)
        print(f"💾 Métriques sauvegardées dans data/temp/metrics_backup.json")
    
    # 4. Enrichissement avec CREATIVES
    if all_data:
        print(f"\n📈 Étape 2: Récupération des creatives...")
        all_data = enrich_ads_with_creatives(all_data, token)
    
    print(f"\n✅ Récupération terminée!")
    print(f"📊 Total: {len(all_data)} ads de {completed - len(failed_accounts)} comptes")
    
    if failed_accounts:
        print(f"⚠️ {len(failed_accounts)} comptes ont échoué: {', '.join(failed_accounts[:5])}")
    
    # 5. Stats sur les formats
    format_counts = defaultdict(int)
    status_counts = defaultdict(int)
    for ad in all_data:
        format_counts[ad.get('format', 'UNKNOWN')] += 1
        status_counts[ad.get('effective_status', 'UNKNOWN')] += 1
    
    print(f"\n📊 Formats détectés:")
    for fmt, count in sorted(format_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  - {fmt}: {count} ads")
    
    print(f"\n📊 Status:")
    for status, count in sorted(status_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
        print(f"  - {status}: {count} ads")
    
    # 6. Sauvegarder les données
    os.makedirs('data/current', exist_ok=True)
    
    # Baseline complète
    baseline = {
        'metadata': {
            'timestamp': datetime.now().isoformat(),
            'reference_date': reference_date,
            'date_range': f"{since_date} to {until_date}",
            'method': 'fetch_sans_demo',
            'total_rows': len(all_data),
            'accounts_processed': len(active_accounts),
            'accounts_success': completed - len(failed_accounts),
            'accounts_failed': len(failed_accounts),
            'has_demographics': False,
            'has_creatives': True
        },
        'daily_ads': all_data
    }
    
    with open('data/current/baseline_90d_daily.json', 'w', encoding='utf-8') as f:
        json.dump(baseline, f, indent=2, ensure_ascii=False)
    
    # 7. Créer les périodes agrégées
    print("\n📊 Génération des périodes...")
    
    for period in [3, 7, 14, 30, 90]:
        # Filtrer par date
        cutoff_date = datetime.strptime(reference_date, '%Y-%m-%d') - timedelta(days=period-1)
        period_ads = [
            ad for ad in all_data 
            if ad.get('date') and datetime.strptime(ad['date'], '%Y-%m-%d') >= cutoff_date
        ]
        
        total_spend = sum(float(ad.get('spend', 0)) for ad in period_ads)
        total_purchases = sum(int(ad.get('purchases', 0)) for ad in period_ads)
        total_value = sum(float(ad.get('purchase_value', 0)) for ad in period_ads)
        active_ads = sum(1 for ad in period_ads if ad.get('effective_status') == 'ACTIVE')
        
        output = {
            'metadata': {
                'timestamp': datetime.now().isoformat(),
                'reference_date': reference_date,
                'period_days': period,
                'total_ads': len(period_ads),
                'active_ads': active_ads,
                'total_spend': total_spend,
                'total_purchases': total_purchases,
                'total_conversion_value': total_value,
                'avg_roas': total_value / total_spend if total_spend > 0 else 0,
                'avg_cpa': total_spend / total_purchases if total_purchases > 0 else 0,
                'has_demographics': False,
                'has_creatives': True
            },
            'ads': period_ads
        }
        
        with open(f'data/current/hybrid_data_{period}d.json', 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        print(f"  ✅ {period}j: {len(period_ads)} ads ({active_ads} actives), ${total_spend:,.0f} MXN")
    
    # 8. Semaine précédente (placeholder pour l'instant)
    prev_output = {
        'metadata': {
            'timestamp': datetime.now().isoformat(),
            'reference_date': (datetime.strptime(reference_date, '%Y-%m-%d') - timedelta(days=7)).strftime('%Y-%m-%d'),
            'period_days': 7,
            'total_ads': 0,
            'has_demographics': False,
            'has_creatives': True
        },
        'ads': []
    }
    
    with open('data/current/hybrid_data_prev_week.json', 'w', encoding='utf-8') as f:
        json.dump(prev_output, f, indent=2, ensure_ascii=False)
    
    # 9. Config
    with open('data/current/refresh_config.json', 'w', encoding='utf-8') as f:
        json.dump({
            "last_update": datetime.now().isoformat(),
            "reference_date": reference_date,
            "periods_available": [3, 7, 14, 30, 90],
            "total_execution_time": time.time() - start_time,
            "accounts_processed": len(active_accounts),
            "accounts_success": completed - len(failed_accounts),
            "total_ads": len(all_data),
            "has_demographics": False,
            "has_creatives": True,
            "formats_detected": dict(format_counts)
        }, f, indent=2)
    
    print(f"\n🎉 TERMINÉ en {(time.time() - start_time)/60:.1f} minutes!")
    print(f"💾 Tous les fichiers dans data/current/")
    print(f"\n📊 Pour Pablo:")
    print(f"  - Active Ads: {sum(1 for ad in all_data if ad.get('effective_status') == 'ACTIVE')}")
    print(f"  - Total Investment: ${sum(float(ad.get('spend', 0)) for ad in all_data):,.0f} MXN")
    print(f"  - Conversion Value: ${sum(float(ad.get('purchase_value', 0)) for ad in all_data):,.0f} MXN")
    print(f"  - ROAS moyen: {sum(float(ad.get('purchase_value', 0)) for ad in all_data) / max(sum(float(ad.get('spend', 0)) for ad in all_data), 1):.2f}")
    
    if len(all_data) > 0:
        print(f"\n✨ Succès! Dashboard prêt avec {len(all_data)} ads")
        print(f"⚠️ Démographies: À récupérer à la demande dans le dashboard")
    else:
        print(f"\n⚠️ Aucune donnée récupérée, vérifiez le token")

if __name__ == '__main__':
    main()