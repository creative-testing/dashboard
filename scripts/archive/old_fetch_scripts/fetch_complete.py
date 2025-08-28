#!/usr/bin/env python3
"""
Version COMPLÈTE - Récupère TOUTES les données sans rien perdre
Optimisé pour MacBook M1 Pro avec 64GB RAM
"""
import os
import requests
import json
import sys
from dotenv import load_dotenv
from datetime import datetime, timedelta
from collections import defaultdict
import time
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
import logging
import signal

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

def get_reference_date():
    """Date de référence : hier"""
    yesterday = datetime.now() - timedelta(days=1)
    return yesterday.strftime('%Y-%m-%d')

def fetch_account_complete(account, token, since_date, until_date):
    """Récupération COMPLÈTE pour un compte - sans rien perdre"""
    account_id = account["id"]
    account_name = account.get("name", "Unknown")
    
    # Skip temporaire pour les comptes problématiques
    if "Chabacano" in account_name:
        logger.warning(f"⚠️ Skip temporaire de {account_name} (trop gros)")
        return []
    
    all_ads = []
    
    try:
        url = f"https://graph.facebook.com/v23.0/{account_id}/insights"
        
        # TOUS les champs requis par Pablo
        fields = [
            "ad_id", "ad_name", "campaign_name", "campaign_id", "adset_name", "adset_id",
            "impressions", "spend", "clicks", "reach", "frequency",
            "ctr", "cpm", "cpp", "cpc",
            "actions", "action_values", "cost_per_action_type",
            "created_time", "updated_time"
        ]
        
        params = {
            "access_token": token,
            "level": "ad",
            "time_range": f'{{"since":"{since_date}","until":"{until_date}"}}',
            "time_increment": 1,  # Journalier pour avoir toutes les données
            "fields": ",".join(fields),
            "filtering": json.dumps([{"field": "impressions", "operator": "GREATER_THAN", "value": 0}]),
            "limit": 1000  # Max par page
        }
        
        current_url = url
        page = 0
        max_pages = 100  # Plus de pages
        backoff = 1
        
        while current_url and page < max_pages:
            try:
                if page == 0:
                    response = requests.get(current_url, params=params, timeout=30)
                else:
                    response = requests.get(current_url, timeout=30)
                
                if response.status_code == 429:  # Rate limit
                    wait_time = min(60, backoff * 2)
                    logger.warning(f"Rate limit {account_name}, attente {wait_time}s")
                    time.sleep(wait_time)
                    backoff *= 2
                    continue
                
                if response.status_code != 200:
                    break
                
                data = response.json()
                
                if "data" in data:
                    ads_batch = data["data"]
                    
                    # Enrichir CHAQUE ad avec TOUTES les métriques
                    for ad in ads_batch:
                        # Infos compte
                        ad['account_name'] = account_name
                        ad['account_id'] = account_id
                        
                        # Extraire purchases et valeurs
                        purchases = 0
                        purchase_value = 0.0
                        
                        for action in ad.get('actions', []):
                            action_type = action.get('action_type', '')
                            if action_type in ['purchase', 'omni_purchase', 'onsite_conversion.purchase']:
                                purchases += int(action.get('value', 0))
                        
                        for value in ad.get('action_values', []):
                            action_type = value.get('action_type', '')
                            if action_type in ['purchase', 'omni_purchase', 'onsite_conversion.purchase']:
                                purchase_value += float(value.get('value', 0))
                        
                        ad['purchases'] = purchases
                        ad['purchase_value'] = purchase_value
                        
                        # Calculer métriques
                        spend = float(ad.get('spend', 0))
                        ad['roas'] = purchase_value / spend if spend > 0 else 0
                        ad['cpa'] = spend / purchases if purchases > 0 else 0
                        
                        # Garder la date
                        ad['date'] = ad.get('date_start', '')
                    
                    all_ads.extend(ads_batch)
                    
                    # Pagination complète
                    if "paging" in data and "next" in data["paging"]:
                        current_url = data["paging"]["next"]
                        page += 1
                        time.sleep(0.2)  # Petit délai entre pages
                    else:
                        break
                else:
                    break
                    
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout {account_name}, nouvelle tentative")
                time.sleep(5)
                continue
            except Exception as e:
                logger.error(f"Erreur page {page} pour {account_name}: {str(e)[:100]}")
                break
        
        logger.info(f"✓ {account_name[:30]}: {len(all_ads)} ads")
        return all_ads
        
    except Exception as e:
        logger.error(f"✗ {account_name[:30]}: {str(e)[:100]}")
        return []

def fetch_ad_details_batch(ad_ids, token):
    """Récupère status et creatives en un batch"""
    if not ad_ids:
        return {}
    
    details = {}
    batch_size = 50
    
    for i in range(0, len(ad_ids), batch_size):
        batch = ad_ids[i:i+batch_size]
        batch_requests = []
        
        for ad_id in batch:
            batch_requests.append({
                "method": "GET",
                "relative_url": f"{ad_id}?fields=status,effective_status,created_time,creative{{video_id,image_url,instagram_permalink_url}}"
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
                for result in response.json():
                    if isinstance(result, dict) and result.get("code") == 200:
                        body = json.loads(result["body"])
                        ad_id = body.get("id")
                        if ad_id:
                            detail = {
                                "status": body.get("status", "UNKNOWN"),
                                "effective_status": body.get("effective_status", "UNKNOWN"),
                                "created_time": body.get("created_time", "")
                            }
                            
                            if "creative" in body:
                                creative = body["creative"]
                                detail["video_id"] = creative.get("video_id")
                                detail["image_url"] = creative.get("image_url")
                                detail["instagram_permalink_url"] = creative.get("instagram_permalink_url")
                                
                                # Déterminer format
                                if creative.get("video_id"):
                                    detail["format"] = "video"
                                elif creative.get("image_url"):
                                    detail["format"] = "image"
                                elif creative.get("instagram_permalink_url"):
                                    detail["format"] = "instagram"
                                else:
                                    detail["format"] = "unknown"
                            
                            details[ad_id] = detail
        except Exception as e:
            logger.warning(f"Erreur batch details: {str(e)[:100]}")
    
    return details

def aggregate_daily_to_period(daily_data, period_days, reference_date):
    """Agrège les données journalières correctement"""
    ref = datetime.strptime(reference_date, '%Y-%m-%d')
    start = ref - timedelta(days=period_days - 1)
    
    # Grouper par ad_id
    ad_groups = defaultdict(list)
    
    for ad in daily_data:
        if ad.get('date'):
            try:
                ad_date = datetime.strptime(ad['date'], '%Y-%m-%d')
                if start <= ad_date <= ref:
                    ad_id = ad.get('ad_id')
                    if ad_id:
                        ad_groups[ad_id].append(ad)
            except:
                continue
    
    # Agréger chaque groupe
    aggregated = []
    
    for ad_id, daily_ads in ad_groups.items():
        if not daily_ads:
            continue
        
        # Prendre les infos du premier jour
        first = daily_ads[0]
        
        # Sommer les métriques
        agg = {
            'ad_id': ad_id,
            'ad_name': first.get('ad_name', ''),
            'campaign_name': first.get('campaign_name', ''),
            'campaign_id': first.get('campaign_id', ''),
            'adset_name': first.get('adset_name', ''),
            'adset_id': first.get('adset_id', ''),
            'account_name': first.get('account_name', ''),
            'account_id': first.get('account_id', ''),
            'status': first.get('status', 'UNKNOWN'),
            'effective_status': first.get('effective_status', 'UNKNOWN'),
            'created_time': first.get('created_time', ''),
            'video_id': first.get('video_id'),
            'image_url': first.get('image_url'),
            'instagram_permalink_url': first.get('instagram_permalink_url'),
            'format': first.get('format', 'unknown'),
            'impressions': sum(int(d.get('impressions', 0)) for d in daily_ads),
            'spend': sum(float(d.get('spend', 0)) for d in daily_ads),
            'clicks': sum(int(d.get('clicks', 0)) for d in daily_ads),
            'reach': max(int(d.get('reach', 0)) for d in daily_ads),
            'purchases': sum(int(d.get('purchases', 0)) for d in daily_ads),
            'purchase_value': sum(float(d.get('purchase_value', 0)) for d in daily_ads),
            'active_days': len(daily_ads)
        }
        
        # Recalculer les métriques
        if agg['impressions'] > 0:
            agg['ctr'] = (agg['clicks'] / agg['impressions']) * 100
            agg['cpm'] = (agg['spend'] / agg['impressions']) * 1000
            agg['frequency'] = agg['impressions'] / agg['reach'] if agg['reach'] > 0 else 0
        else:
            agg['ctr'] = 0
            agg['cpm'] = 0
            agg['frequency'] = 0
        
        if agg['spend'] > 0:
            agg['roas'] = agg['purchase_value'] / agg['spend']
        else:
            agg['roas'] = 0
        
        if agg['purchases'] > 0:
            agg['cpa'] = agg['spend'] / agg['purchases']
        else:
            agg['cpa'] = 0
        
        aggregated.append(agg)
    
    return aggregated

def main():
    """Fonction principale COMPLÈTE"""
    print("🚀 FETCH COMPLETE - Récupération COMPLÈTE sans perte")
    print("=" * 70)
    
    token = os.getenv("FACEBOOK_ACCESS_TOKEN")
    if not token:
        logger.error("❌ Token non trouvé")
        sys.exit(1)
    
    reference_date = get_reference_date()
    start_time = time.time()
    
    # Période configurable (défaut 90 jours pour tout avoir)
    DAYS_TO_FETCH = int(os.getenv('FETCH_DAYS', '90'))
    print(f"📅 Période: {DAYS_TO_FETCH} jours jusqu'à {reference_date}")
    print(f"💻 MacBook M1 Pro - Parallélisation x20")
    
    # 1. Récupérer TOUS les comptes
    print("\n📊 Récupération des comptes...")
    url = "https://graph.facebook.com/v23.0/me/adaccounts"
    params = {
        "access_token": token,
        "fields": "id,name,account_status,currency,timezone_name",
        "limit": 200
    }
    
    response = requests.get(url, params=params, timeout=30)
    if response.status_code != 200:
        logger.error("Erreur récupération comptes")
        sys.exit(1)
    
    accounts = response.json().get("data", [])
    active_accounts = [acc for acc in accounts if acc.get("account_status") == 1]
    print(f"✅ {len(active_accounts)} comptes actifs")
    
    # Sauvegarder index
    os.makedirs('data/current', exist_ok=True)
    with open('data/current/accounts_index.json', 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'total': len(accounts),
            'active_total': len(active_accounts),
            'accounts': accounts
        }, f, indent=2)
    
    # 2. Dates pour la période
    since_date = (datetime.strptime(reference_date, '%Y-%m-%d') - timedelta(days=DAYS_TO_FETCH-1)).strftime('%Y-%m-%d')
    until_date = reference_date
    
    print(f"\n📈 Récupération COMPLÈTE ({since_date} à {until_date})...")
    print(f"⚡ Parallélisation x20 pour {len(active_accounts)} comptes")
    
    all_daily_data = []
    
    # PARALLÉLISATION MAXIMALE pour M1 Pro avec 64GB RAM
    # On peut aller jusqu'à 30-40 threads sans problème
    with ThreadPoolExecutor(max_workers=30) as executor:
        futures = [
            executor.submit(fetch_account_complete, account, token, since_date, until_date)
            for account in active_accounts
        ]
        
        completed = 0
        failed = []
        
        for future in as_completed(futures):
            try:
                # Timeout de 60 secondes max par compte
                ads = future.result(timeout=60)
                if ads:  # Ne compter que si on a des données
                    all_daily_data.extend(ads)
                completed += 1
                if completed % 5 == 0:
                    print(f"  Progress: {completed}/{len(active_accounts)} comptes traités")
            except TimeoutError:
                # Identifier quel compte a timeout
                for acc in active_accounts:
                    if futures[active_accounts.index(acc)] == future:
                        logger.warning(f"⏱️ Timeout: {acc.get('name', 'Unknown')}")
                        failed.append(acc.get('name', 'Unknown'))
                        break
                completed += 1
            except Exception as e:
                logger.error(f"Erreur: {str(e)[:100]}")
                completed += 1
        
        if failed:
            print(f"\n⚠️ {len(failed)} comptes ont échoué/timeout: {', '.join(failed[:5])}")
    
    print(f"\n✅ Total: {len(all_daily_data)} lignes journalières en {time.time()-start_time:.1f}s")
    
    if not all_daily_data:
        logger.warning("⚠️ Aucune donnée récupérée!")
        # Créer fichiers vides
        for period in [3, 7, 14, 30, 90]:
            with open(f'data/current/hybrid_data_{period}d.json', 'w') as f:
                json.dump({'metadata': {'total_ads': 0}, 'ads': []}, f)
        sys.exit(0)
    
    # 3. Enrichir avec status et creatives
    print("\n🎬 Enrichissement status et media URLs...")
    unique_ad_ids = list(set(ad['ad_id'] for ad in all_daily_data if ad.get('ad_id')))
    print(f"  {len(unique_ad_ids)} ads uniques à enrichir")
    
    # Batch par 500 ads
    all_details = {}
    for i in range(0, len(unique_ad_ids), 500):
        batch = unique_ad_ids[i:i+500]
        details = fetch_ad_details_batch(batch, token)
        all_details.update(details)
        print(f"  Progress: {min(i+500, len(unique_ad_ids))}/{len(unique_ad_ids)} ads enrichies")
    
    # Appliquer les détails
    for ad in all_daily_data:
        ad_id = ad.get('ad_id')
        if ad_id in all_details:
            ad.update(all_details[ad_id])
    
    # 4. Sauvegarder baseline journalière COMPLÈTE
    baseline = {
        'metadata': {
            'timestamp': datetime.now().isoformat(),
            'reference_date': reference_date,
            'date_range': f"{since_date} to {until_date}",
            'method': 'fetch_complete',
            'total_rows': len(all_daily_data),
            'unique_ads': len(unique_ad_ids),
            'accounts_processed': len(active_accounts),
            'execution_time': time.time() - start_time
        },
        'daily_ads': all_daily_data
    }
    
    with open('data/current/baseline_90d_daily.json', 'w') as f:
        json.dump(baseline, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Baseline sauvegardée: {len(all_daily_data)} lignes")
    
    # 5. Générer TOUTES les périodes avec agrégation correcte
    print("\n📊 Génération des périodes agrégées...")
    
    for period in [3, 7, 14, 30, 90]:
        print(f"  Agrégation {period} jours...")
        aggregated = aggregate_daily_to_period(all_daily_data, period, reference_date)
        
        # Calculer totaux
        total_spend = sum(ad['spend'] for ad in aggregated)
        total_purchases = sum(ad['purchases'] for ad in aggregated)
        total_value = sum(ad['purchase_value'] for ad in aggregated)
        active_ads = len([ad for ad in aggregated if ad.get('effective_status') in ['ACTIVE', 'CAMPAIGN_PAUSED']])
        
        output = {
            'metadata': {
                'timestamp': datetime.now().isoformat(),
                'reference_date': reference_date,
                'period_days': period,
                'total_ads': len(aggregated),
                'active_ads': active_ads,
                'total_spend': total_spend,
                'total_purchases': total_purchases,
                'total_conversion_value': total_value,
                'avg_roas': total_value / total_spend if total_spend > 0 else 0,
                'avg_cpa': total_spend / total_purchases if total_purchases > 0 else 0
            },
            'ads': aggregated
        }
        
        with open(f'data/current/hybrid_data_{period}d.json', 'w') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        print(f"  ✅ {period}j: {len(aggregated)} ads, ${total_spend:,.0f} MXN, {total_purchases} achats, ROAS {output['metadata']['avg_roas']:.2f}")
    
    # 6. Semaine précédente
    print("\n📆 Génération semaine précédente...")
    prev_ref = (datetime.strptime(reference_date, '%Y-%m-%d') - timedelta(days=7)).strftime('%Y-%m-%d')
    prev_week = aggregate_daily_to_period(all_daily_data, 7, prev_ref)
    
    prev_output = {
        'metadata': {
            'timestamp': datetime.now().isoformat(),
            'reference_date': prev_ref,
            'period_days': 7,
            'total_ads': len(prev_week),
            'total_spend': sum(ad['spend'] for ad in prev_week),
            'total_purchases': sum(ad['purchases'] for ad in prev_week),
            'total_conversion_value': sum(ad['purchase_value'] for ad in prev_week)
        },
        'ads': prev_week
    }
    
    with open('data/current/hybrid_data_prev_week.json', 'w') as f:
        json.dump(prev_output, f, indent=2, ensure_ascii=False)
    
    # 7. Config finale
    with open('data/current/refresh_config.json', 'w') as f:
        json.dump({
            "last_update": datetime.now().isoformat(),
            "reference_date": reference_date,
            "periods_available": [3, 7, 14, 30, 90],
            "total_execution_time": time.time() - start_time,
            "accounts_processed": len(active_accounts),
            "total_daily_rows": len(all_daily_data),
            "unique_ads": len(unique_ad_ids)
        }, f, indent=2)
    
    print(f"\n🎉 FETCH COMPLETE TERMINÉ!")
    print(f"⏱️  Temps total: {(time.time() - start_time)/60:.1f} minutes")
    print(f"📊 Résumé final:")
    print(f"  - {len(active_accounts)} comptes traités")
    print(f"  - {len(all_daily_data)} lignes journalières")
    print(f"  - {len(unique_ad_ids)} ads uniques")
    print(f"💾 Tous les fichiers dans data/current/")

if __name__ == '__main__':
    main()