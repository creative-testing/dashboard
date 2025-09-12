#!/usr/bin/env python3
"""
Version améliorée du fetch avec gestion intelligente des rate limits
Implémente les recommandations des assistants de recherche :
- Monitoring proactif des headers
- Exponential backoff avec jitter
- Jobs asynchrones pour les grosses requêtes
- Adaptation dynamique des workers

⚠️ IMPORTANT: Ce script nécessite un TIMEOUT MINIMUM de 35 minutes
   à cause des pauses proactives et du mode Development Access Tier.
   
   Utilisation recommandée : 
   timeout 2100 python fetch_with_smart_limits.py
   ou avec nohup :
   nohup python fetch_with_smart_limits.py > fetch.log 2>&1 &
"""
import os
import sys
import json
import time
import logging
import requests
import random
from datetime import datetime, timedelta
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional
from dotenv import load_dotenv

# Ajouter le parent directory au path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.rate_limit_manager import RateLimitManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

class SmartMetaFetcher:
    """Fetcher intelligent avec gestion avancée des rate limits"""
    
    def __init__(self, token: str, development_mode: bool = True):
        self.token = token
        self.rate_limiter = RateLimitManager(development_mode)
        self.base_url = "https://graph.facebook.com/v23.0"
        self.retry_attempts = {}  # Track retries par compte
        
    def exponential_backoff(self, attempt: int, base_delay: float = 2.0) -> float:
        """Calcule le délai avec exponential backoff + jitter"""
        # Formule: base * 2^attempt avec jitter ±25%
        delay = base_delay * (2 ** attempt)
        jitter = random.uniform(0.75, 1.25)
        return min(delay * jitter, 300)  # Max 5 minutes
    
    def make_api_call(self, url: str, params: dict, account_id: str, method: str = 'GET') -> Optional[dict]:
        """Fait un appel API avec gestion intelligente des erreurs"""
        
        attempt = self.retry_attempts.get(account_id, 0)
        max_attempts = 5
        
        while attempt < max_attempts:
            try:
                # Faire la requête
                if method == 'GET':
                    response = requests.get(url, params=params, timeout=120)
                else:
                    response = requests.post(url, data=params, timeout=120)
                
                # Parser les headers de rate limit AVANT de vérifier le status
                if response.headers:
                    self.rate_limiter.apply_smart_delay(account_id, response.headers)
                
                # Gérer les différents codes de réponse
                if response.status_code == 200:
                    self.retry_attempts[account_id] = 0  # Reset on success
                    return response.json()
                
                elif response.status_code == 429:  # Rate limit
                    wait_time = self.exponential_backoff(attempt, base_delay=30)
                    logger.warning(f"  ⏰ Rate limit (429) pour {account_id}, "
                                 f"attente {wait_time:.1f}s (tentative {attempt+1}/{max_attempts})")
                    time.sleep(wait_time)
                    attempt += 1
                    
                elif response.status_code == 500:  # Server error
                    wait_time = self.exponential_backoff(attempt, base_delay=10)
                    logger.warning(f"  🔄 Erreur serveur (500) pour {account_id}, "
                                 f"attente {wait_time:.1f}s (tentative {attempt+1}/{max_attempts})")
                    time.sleep(wait_time)
                    attempt += 1
                    
                elif response.status_code == 400:  # Bad request
                    error_data = response.json().get('error', {})
                    error_code = error_data.get('code')
                    
                    if error_code == 80004:  # Too many calls
                        # Utiliser estimated_time_to_regain_access si disponible
                        wait_time = error_data.get('estimated_time_to_regain_access', 5) * 60
                        if wait_time == 0:
                            wait_time = self.exponential_backoff(attempt, base_delay=60)
                        
                        logger.warning(f"  🚫 Error #80004 pour {account_id}, "
                                     f"attente {wait_time:.1f}s")
                        time.sleep(wait_time)
                        attempt += 1
                    else:
                        logger.error(f"  ❌ Erreur 400 pour {account_id}: {error_data.get('message', 'Unknown')}")
                        break
                        
                else:
                    logger.error(f"  ❌ Erreur {response.status_code} pour {account_id}")
                    break
                    
            except requests.exceptions.Timeout:
                wait_time = self.exponential_backoff(attempt, base_delay=5)
                logger.warning(f"  ⏱️ Timeout pour {account_id}, attente {wait_time:.1f}s")
                time.sleep(wait_time)
                attempt += 1
                
            except Exception as e:
                logger.error(f"  ❌ Erreur inattendue pour {account_id}: {str(e)[:100]}")
                break
        
        self.retry_attempts[account_id] = attempt
        return None
    
    def create_async_insights_job(self, account_id: str, since_date: str, until_date: str) -> Optional[str]:
        """Crée un job asynchrone pour les insights (recommandé pour gros volumes)"""
        
        url = f"{self.base_url}/act_{account_id}/insights"
        
        params = {
            "access_token": self.token,
            "level": "ad",
            "time_range": json.dumps({"since": since_date, "until": until_date}),
            "time_increment": "1",
            "fields": "ad_id,ad_name,campaign_name,campaign_id,adset_name,adset_id,impressions,spend,clicks,reach,frequency,actions,action_values,conversions,conversion_values,created_time",
            "limit": 5000,
            # Aligner sur Facebook Ads Manager
            "action_report_time": os.getenv("ACTION_REPORT_TIME", "conversion")
        }
        
        # Filtre impressions optionnel (OFF par défaut car peut cacher des conversions)
        if os.getenv("FILTER_IMPR_GT0", "0") == "1":
            params["filtering"] = json.dumps([{"field": "impressions", "operator": "GREATER_THAN", "value": 0}])
        
        # Attribution : utiliser soit unified, soit windows (pas les deux)
        USE_UNIFIED = os.getenv("USE_UNIFIED_ATTR", "1") == "1"
        if USE_UNIFIED:
            params["use_unified_attribution_setting"] = "true"
        else:
            params["action_attribution_windows"] = json.dumps(
                os.getenv("ACTION_ATTR_WINDOWS", "7d_click,1d_view").split(",")
            )
        
        logger.info(f"  🚀 Création job async pour {account_id}...")
        
        response_data = self.make_api_call(url, params, account_id, method='POST')
        
        if response_data and 'report_run_id' in response_data:
            report_id = response_data['report_run_id']
            logger.info(f"  ✅ Job créé: {report_id}")
            return report_id
        
        return None
    
    def wait_for_async_job(self, report_id: str, account_id: str) -> Optional[dict]:
        """Attend qu'un job async soit terminé et récupère les résultats"""
        
        status_url = f"{self.base_url}/{report_id}"
        max_wait = 600  # 10 minutes max
        start_time = time.time()
        check_interval = 5  # Commence par vérifier toutes les 5 secondes
        
        while (time.time() - start_time) < max_wait:
            params = {"access_token": self.token}
            response_data = self.make_api_call(status_url, params, account_id)
            
            if not response_data:
                return None
            
            status = response_data.get('async_status')
            percent = response_data.get('async_percent_completion', 0)
            
            logger.info(f"  ⏳ Job {report_id}: {status} ({percent}%)")
            
            if status == 'Job Completed':
                # Récupérer les résultats
                results_url = f"{self.base_url}/{report_id}/insights"
                all_results = []
                
                while results_url:
                    response_data = self.make_api_call(results_url, params, account_id)
                    if not response_data:
                        break
                    
                    all_results.extend(response_data.get('data', []))
                    
                    # Pagination
                    if 'paging' in response_data and 'next' in response_data['paging']:
                        results_url = response_data['paging']['next']
                    else:
                        break
                
                logger.info(f"  ✅ Job terminé: {len(all_results)} ads récupérées")
                return {'data': all_results}
                
            elif status in ['Job Failed', 'Job Skipped']:
                logger.error(f"  ❌ Job échoué: {status}")
                return None
            
            # Backoff progressif pour les checks
            time.sleep(min(check_interval, 30))
            check_interval = min(check_interval * 1.5, 30)  # Augmente jusqu'à 30s max
        
        logger.error(f"  ⏱️ Timeout pour job {report_id}")
        return None
    
    def fetch_account_insights(self, account: dict, since_date: str, until_date: str, use_async: bool = False) -> List[dict]:
        """Récupère les insights d'un compte avec stratégie adaptative"""
        
        account_id = account["id"].replace("act_", "")
        account_name = account.get("name", "Unknown")
        
        # Calculer le nombre de jours
        days_diff = (datetime.strptime(until_date, '%Y-%m-%d') - 
                    datetime.strptime(since_date, '%Y-%m-%d')).days
        
        # Utiliser async pour les grosses requêtes (>30 jours ou si demandé)
        if use_async or days_diff > 30:
            logger.info(f"📊 {account_name}: Utilisation du mode ASYNC ({days_diff} jours)")
            
            # Créer le job
            report_id = self.create_async_insights_job(account_id, since_date, until_date)
            if report_id:
                # Attendre et récupérer les résultats
                result = self.wait_for_async_job(report_id, account_id)
                if result:
                    ads = result.get('data', [])
                    # Enrichir avec les infos du compte
                    for ad in ads:
                        ad['account_name'] = account_name
                        ad['account_id'] = account_id
                        # Process purchases...
                        self._process_purchases(ad)
                    return ads
            
            logger.warning(f"  ⚠️ Échec async pour {account_name}, fallback sur sync")
        
        # Mode synchrone (pour petites requêtes ou fallback)
        return self._fetch_sync(account, since_date, until_date)
    
    def _fetch_sync(self, account: dict, since_date: str, until_date: str) -> List[dict]:
        """Fetch synchrone classique avec pagination"""
        account_id = account["id"].replace("act_", "")
        account_name = account.get("name", "Unknown")
        
        all_ads = []
        url = f"{self.base_url}/act_{account_id}/insights"
        
        # Adapter la taille du batch selon l'usage
        batch_size = self.rate_limiter.get_optimal_batch_size(account_id)
        
        params = {
            "access_token": self.token,
            "level": "ad",
            "time_range": json.dumps({"since": since_date, "until": until_date}),
            "time_increment": "1",
            "fields": "ad_id,ad_name,campaign_name,campaign_id,adset_name,adset_id,impressions,spend,clicks,reach,frequency,actions,action_values,conversions,conversion_values,created_time",
            "limit": batch_size,
            # Aligner sur Facebook Ads Manager
            "action_report_time": os.getenv("ACTION_REPORT_TIME", "conversion")
        }
        
        # Filtre impressions optionnel (OFF par défaut car peut cacher des conversions)
        if os.getenv("FILTER_IMPR_GT0", "0") == "1":
            params["filtering"] = json.dumps([{"field": "impressions", "operator": "GREATER_THAN", "value": 0}])
        
        # Attribution : utiliser soit unified, soit windows (pas les deux)
        USE_UNIFIED = os.getenv("USE_UNIFIED_ATTR", "1") == "1"
        if USE_UNIFIED:
            params["use_unified_attribution_setting"] = "true"
        else:
            params["action_attribution_windows"] = json.dumps(
                os.getenv("ACTION_ATTR_WINDOWS", "7d_click,1d_view").split(",")
            )
        
        page = 0
        max_pages = 100
        
        while page < max_pages:
            response_data = self.make_api_call(url, params, account_id)
            
            if not response_data:
                break
            
            if "data" in response_data:
                ads_batch = response_data["data"]
                
                for ad in ads_batch:
                    ad['account_name'] = account_name
                    ad['account_id'] = account_id
                    self._process_purchases(ad)
                
                all_ads.extend(ads_batch)
                
                # Pagination
                if "paging" in response_data and "next" in response_data["paging"]:
                    url = response_data["paging"]["next"]
                    params = {}  # Les params sont dans l'URL next
                    page += 1
                    
                    # Pause adaptative entre les pages
                    pause = 0.5 if not self.rate_limiter.development_mode else 1.0
                    time.sleep(pause)
                else:
                    break
            else:
                break
        
        logger.info(f"✓ {account_name[:30]}: {len(all_ads)} ads (métriques)")
        return all_ads
    
    def fetch_creatives_batch(self, ad_ids: List[str]) -> Dict[str, dict]:
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
            params = {
                "access_token": self.token,
                "batch": json.dumps(batch_requests)
            }
            
            response = requests.post(self.base_url, data=params, timeout=60)
            
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
                        # NOTE: Instagram carousel URLs require user to be logged in to Instagram
                        # They will show "Post isn't available" if not authenticated
                        # This is NOT a bug - it's Instagram's expected behavior
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
    
    def enrich_ads_with_creatives(self, ads: List[dict]) -> List[dict]:
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
                futures.append(executor.submit(self.fetch_creatives_batch, batch))
            
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
                # Valeurs par défaut SEULEMENT si pas de données creative
                ad.setdefault('status', 'UNKNOWN')
                ad.setdefault('effective_status', 'UNKNOWN')
                ad.setdefault('format', 'UNKNOWN')
                ad.setdefault('media_url', '')
                ad.setdefault('creative_status', 'UNKNOWN')
        
        logger.info(f"✅ {enriched}/{len(ads)} ads enrichies avec creatives")
        return ads
    
    def _process_purchases(self, ad: dict):
        """Traite les données d'achats d'une ad - Priorise omni_purchase"""
        # Ordre canonique recommandé (omni_purchase en premier)
        PURCHASE_KEYS = [
            'omni_purchase',
            'purchase', 
            'offsite_conversion.fb_pixel_purchase',
            'onsite_conversion.purchase',
            'onsite_web_purchase'
        ]
        
        def _map_values(items):
            """Crée un dictionnaire des valeurs par action_type"""
            return {i.get('action_type', ''): float(i.get('value', 0) or 0) for i in (items or [])}
        
        # 1) Préférer 'conversions'/'conversion_values' si disponibles
        conv_map = _map_values(ad.get('conversions', []))
        conv_val_map = _map_values(ad.get('conversion_values', []))
        
        # 2) Sinon fallback sur 'actions'/'action_values'
        act_map = _map_values(ad.get('actions', [])) if not conv_map else {}
        act_val_map = _map_values(ad.get('action_values', [])) if not conv_val_map else {}
        
        def _pick_first(mapping, keys):
            """Prend la première valeur trouvée dans l'ordre de priorité"""
            for k in keys:
                if k in mapping and mapping[k] > 0:
                    return mapping[k]
            return 0.0
        
        # Utiliser conversions en priorité, sinon actions
        purchases = _pick_first(conv_map or act_map, PURCHASE_KEYS)
        purchase_value = _pick_first(conv_val_map or act_val_map, PURCHASE_KEYS)
        
        ad['purchases'] = int(round(purchases))
        ad['purchase_value'] = float(purchase_value)
        
        spend = float(ad.get('spend', 0) or 0)
        ad['roas'] = (ad['purchase_value'] / spend) if spend > 0 else 0.0
        ad['cpa'] = (spend / ad['purchases']) if ad['purchases'] > 0 else 0.0
        ad['date'] = ad.get('date_start', '')

def main():
    """Fonction principale avec gestion intelligente des rate limits"""
    print("🎯 FETCH INTELLIGENT - Gestion avancée des rate limits")
    print("=" * 70)
    
    start_time = time.time()  # Démarrer le chrono
    
    token = os.getenv("FACEBOOK_ACCESS_TOKEN")
    if not token:
        logger.error("❌ Token non trouvé dans .env")
        sys.exit(1)
    
    # Détecter si on est en mode dev (basé sur les erreurs précédentes)
    development_mode = True  # On sait qu'on est en dev d'après les erreurs
    
    fetcher = SmartMetaFetcher(token, development_mode)
    
    print(f"📊 Mode: {'DEVELOPMENT' if development_mode else 'PRODUCTION'}")
    print(f"⚠️ Limites strictes activées, utilisation de stratégies adaptatives")
    
    # Récupérer les comptes
    print("\n📋 Récupération des comptes...")
    accounts_url = f"{fetcher.base_url}/me/adaccounts"
    accounts_params = {
        "access_token": token,
        "fields": "id,name,account_status",
        "limit": 200
    }
    
    response = requests.get(accounts_url, params=accounts_params, timeout=30)
    if response.status_code != 200:
        logger.error(f"Erreur récupération comptes: {response.status_code}")
        # Si rate limit dès le début, attendre
        if response.status_code == 400:
            error = response.json().get('error', {})
            if error.get('code') == 80004:
                wait_time = error.get('estimated_time_to_regain_access', 15) * 60
                print(f"\n⏰ Rate limit détecté, attente de {wait_time/60:.1f} minutes...")
                print("💡 Conseil: Relancer le script plus tard ou utiliser un autre token")
                sys.exit(1)
        sys.exit(1)
    
    accounts = response.json().get("data", [])
    active_accounts = [acc for acc in accounts if acc.get("account_status") == 1]
    print(f"✅ {len(active_accounts)} comptes actifs trouvés")
    
    # LOG DETAILED ACCOUNT INFO FOR DEBUGGING
    print(f"\n📊 DETAILED ACCOUNT LIST:")
    for acc in active_accounts:
        print(f"  - {acc.get('name', 'Unknown')} (ID: {acc.get('id', 'N/A')})")
    
    # Configuration de fraîcheur
    BUFFER_HOURS = int(os.getenv('FRESHNESS_BUFFER_HOURS', '3'))
    TAIL_BACKFILL_DAYS = int(os.getenv('TAIL_BACKFILL_DAYS', '3'))
    BASELINE_DAYS = int(os.getenv('FETCH_DAYS', '90'))
    
    # Aligner sur Ads Manager (exclure aujourd'hui par défaut)
    INCLUDE_TODAY = os.getenv('INCLUDE_TODAY', '0') == '1'
    
    # High-watermark date (aligné sur Ads Manager)
    if INCLUDE_TODAY:
        # Mode ancien : inclure aujourd'hui (avec buffer)
        high_watermark_datetime = datetime.now() - timedelta(hours=BUFFER_HOURS)
    else:
        # Mode Ads Manager : exclure aujourd'hui (jusqu'à hier 23:59:59)
        high_watermark_datetime = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(seconds=1)
    
    reference_date = high_watermark_datetime.strftime('%Y-%m-%d')
    reference_hour = high_watermark_datetime.strftime('%Y-%m-%d %H:%M:%S')
    
    # Déterminer si on fait tail only ou baseline complet
    run_baseline = os.getenv('RUN_BASELINE', '0') == '1'
    
    if run_baseline:
        # Baseline complet (ex: nuit ou toutes les X heures)
        days_to_fetch = BASELINE_DAYS
        since_date = (datetime.strptime(reference_date, '%Y-%m-%d') - timedelta(days=days_to_fetch-1)).strftime('%Y-%m-%d')
        until_date = reference_date
        print(f"\n📚 Mode BASELINE: {since_date} à {until_date} ({days_to_fetch} jours)")
    else:
        # Tail refresh seulement (par défaut, plus fréquent)
        days_to_fetch = TAIL_BACKFILL_DAYS
        since_date = (datetime.strptime(reference_date, '%Y-%m-%d') - timedelta(days=days_to_fetch-1)).strftime('%Y-%m-%d')
        until_date = reference_date
        print(f"\n⚡ Mode TAIL: {since_date} à {until_date} ({days_to_fetch} jours, buffer {BUFFER_HOURS}h)")
    
    print(f"🕰️ Données jusqu'à: {reference_hour} (maintenant - {BUFFER_HOURS}h)")
    print(f"📅 Période: {since_date} à {until_date} ({days_to_fetch} jours)")
    
    # Stratégie adaptative
    use_async = days_to_fetch > 30  # Async pour les grosses périodes
    initial_workers = 4 if development_mode else 16  # Commence conservateur
    
    print(f"🔧 Stratégie: {'ASYNC' if use_async else 'SYNC'}, {initial_workers} workers initiaux")
    
    all_data = []
    failed_accounts = []
    
    # Phase 1: Fetch initial avec peu de workers
    print(f"\n📈 Phase 1: Récupération initiale...")
    with ThreadPoolExecutor(max_workers=initial_workers) as executor:
        futures = {
            executor.submit(fetcher.fetch_account_insights, account, since_date, until_date, use_async): account
            for account in active_accounts
        }
        
        completed = 0
        for future in as_completed(futures):
            account = futures[future]
            try:
                ads = future.result(timeout=300)
                if ads:
                    all_data.extend(ads)
                else:
                    failed_accounts.append(account)
                completed += 1
                
                if completed % 5 == 0:
                    print(f"  Progress: {completed}/{len(active_accounts)} comptes")
                    # Ajuster les workers dynamiquement
                    new_workers = fetcher.rate_limiter.get_worker_count()
                    if new_workers != initial_workers:
                        print(f"  🔧 Ajustement workers: {initial_workers} → {new_workers}")
                        
            except Exception as e:
                logger.error(f"⚠️ Échec {account.get('name', 'Unknown')}: {str(e)[:50]}")
                failed_accounts.append(account)
                completed += 1
    
    # Phase 2: Retry pour les comptes échoués
    if failed_accounts:
        print(f"\n🔄 Phase 2: Retry pour {len(failed_accounts)} comptes...")
        time.sleep(30)  # Pause avant retry
        
        recovered = []
        for account in failed_accounts:
            logger.info(f"  Retry: {account.get('name', 'Unknown')}")
            ads = fetcher.fetch_account_insights(account, since_date, until_date, use_async=True)
            if ads:
                all_data.extend(ads)
                recovered.append(account)
                logger.info(f"  ✅ Récupéré: {len(ads)} ads")
        
        if recovered:
            print(f"✅ {len(recovered)} comptes récupérés en retry")
    
    # Afficher le résumé des rate limits
    fetcher.rate_limiter.log_summary()
    
    # Enrichissement avec CREATIVES
    if all_data:
        print(f"\n🎨 Étape 2: Récupération des creatives...")
        all_data = fetcher.enrich_ads_with_creatives(all_data)
    
    # Sauvegarder les résultats
    print(f"\n💾 Sauvegarde de {len(all_data)} ads...")
    os.makedirs('data/current', exist_ok=True)
    
    # Charger le baseline existant si mode tail
    existing_baseline = None
    bootstrap_mode = False
    if not run_baseline and os.path.exists('data/current/baseline_90d_daily.json'):
        try:
            with open('data/current/baseline_90d_daily.json', 'r', encoding='utf-8') as f:
                existing_baseline = json.load(f)
                existing_ads_count = len(existing_baseline.get('daily_ads', []))
                print(f"\n🔄 Baseline existant chargé: {existing_ads_count} ads")
                
                # Si baseline vide ou très petit, activer bootstrap
                if existing_ads_count < 100 and os.getenv('BOOTSTRAP_IF_EMPTY') == '1':
                    print(f"\n🚀 BOOTSTRAP MODE: Baseline trop petit ({existing_ads_count} ads)")
                    print(f"    Fetching 30 days to bootstrap the system...")
                    bootstrap_mode = True
                    # Override the backfill days for bootstrap
                    import sys
                    sys.modules[__name__].TAIL_BACKFILL_DAYS = 30
        except Exception as e:
            print(f"⚠️ Impossible de charger le baseline existant: {e}")
    
    # Upsert tail dans baseline si applicable
    if existing_baseline and not run_baseline:
        # Créer un index par (ad_id, date)
        baseline_index = {}
        for idx, ad in enumerate(existing_baseline.get('daily_ads', [])):
            key = (ad.get('ad_id'), ad.get('date'))
            if all(key):
                baseline_index[key] = idx
        
        # Upsert les nouvelles données tail
        updated_count = 0
        added_count = 0
        for ad in all_data:
            key = (ad.get('ad_id'), ad.get('date'))
            if all(key):
                if key in baseline_index:
                    # Remplacer l'existant
                    existing_baseline['daily_ads'][baseline_index[key]] = ad
                    updated_count += 1
                else:
                    # Ajouter nouveau
                    existing_baseline['daily_ads'].append(ad)
                    added_count += 1
        
        print(f"\n✅ Upsert terminé: {updated_count} mis à jour, {added_count} ajoutés")
        all_data = existing_baseline['daily_ads']
    
    baseline = {
        'metadata': {
            'timestamp': datetime.now().isoformat(),
            'reference_date': reference_date,
            'reference_hour': reference_hour,
            'buffer_hours': BUFFER_HOURS,
            'tail_backfill_days': TAIL_BACKFILL_DAYS if not run_baseline else None,
            'mode': 'baseline' if run_baseline else 'tail',
            'date_range': f"{since_date} to {until_date}",
            'method': 'fetch_smart_limits',
            'total_rows': len(all_data),
            'accounts_processed': len(active_accounts),
            'accounts_success': len(active_accounts) - (len(failed_accounts) - len(recovered) if 'recovered' in locals() else len(failed_accounts)),
            'accounts_failed': len(failed_accounts) - len(recovered) if 'recovered' in locals() else len(failed_accounts),
            'has_demographics': False,
            'has_creatives': True,
            'fetch_strategy': 'smart_limits',
            'development_mode': development_mode,
            'includes_today': reference_date == datetime.now().strftime('%Y-%m-%d')
        },
        'daily_ads': all_data
    }
    
    with open('data/current/baseline_90d_daily.json', 'w', encoding='utf-8') as f:
        json.dump(baseline, f, indent=2, ensure_ascii=False)
    
    # Générer prev_week_data.json pour les comparaisons semaine vs semaine
    print("\n📊 Génération de la semaine précédente pour comparaisons...")
    prev_week_end = datetime.strptime(reference_date, '%Y-%m-%d') - timedelta(days=7)
    prev_week_start = prev_week_end - timedelta(days=6)
    
    # Utiliser le baseline complet (qui contient 90 jours) pour trouver la semaine précédente
    # all_data ne contient que les 7 derniers jours, donc on utilise baseline['daily_ads']
    baseline_ads = baseline.get('daily_ads', [])
    prev_week_ads = [
        ad for ad in baseline_ads 
        if ad.get('date') and prev_week_start <= datetime.strptime(ad['date'], '%Y-%m-%d') <= prev_week_end
    ]
    
    if prev_week_ads:
        prev_total_spend = sum(float(ad.get('spend', 0)) for ad in prev_week_ads)
        prev_output = {
            'metadata': {
                'timestamp': datetime.now().isoformat(),
                'reference_date': prev_week_end.strftime('%Y-%m-%d'),
                'date_range': f"{prev_week_start.strftime('%Y-%m-%d')} to {prev_week_end.strftime('%Y-%m-%d')}",
                'period_days': 7,
                'total_ads': len(prev_week_ads)
            },
            'ads': prev_week_ads
        }
        
        with open('data/current/prev_week_data.json', 'w', encoding='utf-8') as f:
            json.dump(prev_output, f, indent=2, ensure_ascii=False)
        
        print(f"  ✅ Semaine précédente: {len(prev_week_ads)} ads, ${prev_total_spend:,.0f}")
    
    print(f"\n🎉 TERMINÉ en {(time.time() - start_time)/60:.1f} minutes!")
    print(f"💾 Tous les fichiers dans data/current/")
    print(f"\n📊 SUMMARY FOR DEBUGGING:")
    print(f"  - Total unique ads fetched: {len(all_data)}")
    print(f"  - Accounts processed: {len(set(ad.get('account_name', '') for ad in all_data))}")
    print(f"  - Active Ads: {sum(1 for ad in all_data if ad.get('effective_status') == 'ACTIVE')}")
    print(f"  - Total Investment: ${sum(float(ad.get('spend', 0)) for ad in all_data):,.0f} MXN")
    print(f"  - Conversion Value: ${sum(float(ad.get('purchase_value', 0)) for ad in all_data):,.0f} MXN")
    print(f"  - ROAS moyen: {sum(float(ad.get('purchase_value', 0)) for ad in all_data) / max(sum(float(ad.get('spend', 0)) for ad in all_data), 1):.2f}")
    
    if len(all_data) > 0:
        # Lancer la compression
        print("\n🗜️ Lancement de la compression...")
        try:
            import subprocess
            import sys
            # Résoudre le chemin de manière robuste
            here = os.path.dirname(os.path.abspath(__file__))
            compress_script = os.path.normpath(os.path.join(here, "compress_after_fetch.py"))
            result = subprocess.run(
                [sys.executable, compress_script, "--input-dir", "data/current"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                print("✅ Compression réussie et dashboard mis à jour")
                # Afficher les lignes importantes du résultat
                for line in result.stdout.split('\n'):
                    if any(word in line for word in ['✅', '📊', 'ratio', 'MB']):
                        print(f"   {line}")
            else:
                print(f"⚠️ Compression échouée: {result.stderr}")
        except Exception as e:
            print(f"⚠️ Erreur lors de la compression: {e}")

if __name__ == '__main__':
    main()