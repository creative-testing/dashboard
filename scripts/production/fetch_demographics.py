#!/usr/bin/env python3
"""
Fetch demographic breakdowns (age/gender) for all accounts.
Suivant les recommandations de ChatGPT-5 Pro :
- Level: adset (pas ad) pour réduire le volume
- Breakdowns: ['age', 'gender']
- Agrégation par période: 7d, 30d, 90d
- Sauvegarde en JSON pré-calculé pour le dashboard
"""
import os
import sys
import json
import time
import logging
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv

# Ajouter le parent directory au path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.rate_limit_manager import RateLimitManager

# Import SmartMetaFetcher from existing script
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_with_smart_limits import SmartMetaFetcher

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

class DemographicsFetcher:
    """Fetcher spécialisé pour les données démographiques avec breakdowns age/gender"""
    
    def __init__(self, token: str, development_mode: bool = True):
        self.fetcher = SmartMetaFetcher(token, development_mode)
        self.base_url = "https://graph.facebook.com/v23.0"
        self.token = token
        
    def fetch_demographics_for_period(
        self, 
        account_id: str, 
        account_name: str,
        since_date: str, 
        until_date: str,
        period_days: int
    ) -> Optional[Dict]:
        """
        Récupère les insights avec breakdowns age/gender pour une période.
        Utilise level=adset pour réduire le volume.
        """
        logger.info(f"📊 Fetching demographics for {account_name} ({period_days}d: {since_date} to {until_date})")
        
        # Pour 90j, utiliser async job
        use_async = period_days >= 90
        
        if use_async:
            # Créer un job async
            report_id = self._create_async_demographics_job(account_id, since_date, until_date)
            if not report_id:
                logger.error(f"  ❌ Failed to create async job for {account_name}")
                return None
            
            # Attendre et récupérer les résultats
            results = self.fetcher.wait_for_async_job(report_id, account_id)
        else:
            # Appel synchrone direct
            results = self._fetch_sync_demographics(account_id, since_date, until_date)
        
        if not results:
            logger.warning(f"  ⚠️ No demographics data for {account_name}")
            return None
            
        # Agréger par segment (age, gender)
        segments = self._aggregate_segments(results)
        
        # Calculer les totaux
        totals = self._calculate_totals(segments)
        
        # Construire le résultat final
        return {
            "metadata": {
                "account_id": account_id,
                "account_name": account_name,
                "period": f"{period_days}d",
                "date_range": f"{since_date}..{until_date}",
                "generated_at": datetime.utcnow().isoformat() + "Z",
                "source": "insights(level=adset, breakdowns=[age,gender])"
            },
            "segments": segments,
            "totals": totals
        }
    
    def _create_async_demographics_job(self, account_id: str, since_date: str, until_date: str) -> Optional[str]:
        """Crée un job async pour les demographics (90d)"""
        url = f"{self.base_url}/act_{account_id}/insights"
        
        params = {
            "access_token": self.token,
            "level": "account",  # BEAUCOUP plus rapide: 1 ligne par segment
            "time_range": json.dumps({"since": since_date, "until": until_date}),
            "breakdowns": json.dumps(["age", "gender"]),  # Le point clé !
            "fields": "impressions,spend,clicks,actions,action_values,date_start",
            "limit": 500,
            "action_report_time": "conversion",
            "use_unified_attribution_setting": "true"
        }
        
        response_data = self.fetcher.make_api_call(url, params, account_id, method='POST')
        
        if response_data and 'report_run_id' in response_data:
            report_id = response_data['report_run_id']
            logger.info(f"  ✅ Async job created: {report_id}")
            return report_id
        
        return None
    
    def _fetch_sync_demographics(self, account_id: str, since_date: str, until_date: str) -> List[Dict]:
        """Fetch synchrone pour périodes courtes (7d, 30d)"""
        url = f"{self.base_url}/act_{account_id}/insights"
        
        params = {
            "access_token": self.token,
            "level": "account",  # BEAUCOUP plus rapide
            "time_range": json.dumps({"since": since_date, "until": until_date}),
            "breakdowns": "age,gender",  # Format string pour sync
            "fields": "impressions,spend,clicks,actions,action_values,date_start",
            "limit": 500,
            "action_report_time": "conversion",
            "use_unified_attribution_setting": "true"
        }
        
        all_results = []
        next_url = None
        
        while True:
            if next_url:
                # Pagination
                response_data = self.fetcher.make_api_call(next_url, {"access_token": self.token}, account_id)
            else:
                response_data = self.fetcher.make_api_call(url, params, account_id)
            
            if not response_data:
                break
                
            all_results.extend(response_data.get('data', []))
            
            # Check pagination
            paging = response_data.get('paging', {})
            next_url = paging.get('next')
            if not next_url:
                break
                
        return all_results
    
    def _extract_purchase_data(self, actions: List[Dict], action_values: List[Dict]) -> Tuple[float, float]:
        """
        Extrait purchases et purchase_value depuis actions/action_values.
        Suit la même logique que fetch_with_smart_limits.py
        """
        purchases = 0.0
        purchase_value = 0.0
        
        # Ordre de priorité pour les conversions
        purchase_keys = [
            'omni_purchase',
            'purchase',
            'onsite_conversion.purchase',
            'offsite_conversion.fb_pixel_purchase',
            'catalog_sale'
        ]
        
        # Extraire purchases (nombre)
        if actions:
            for key in purchase_keys:
                for action in actions:
                    if action.get('action_type') == key:
                        try:
                            purchases = float(action.get('value', 0))
                            break
                        except (TypeError, ValueError):
                            continue
                if purchases > 0:
                    break
        
        # Extraire purchase_value (montant)
        if action_values:
            for key in purchase_keys:
                for action in action_values:
                    if action.get('action_type') == key:
                        try:
                            purchase_value = float(action.get('value', 0))
                            break
                        except (TypeError, ValueError):
                            continue
                if purchase_value > 0:
                    break
        
        return purchases, purchase_value
    
    def _aggregate_segments(self, raw_results: List[Dict]) -> List[Dict]:
        """
        Agrège les résultats journaliers par segment (age, gender).
        Retourne une liste de segments avec métriques calculées.
        """
        segments_map = defaultdict(lambda: {
            'impressions': 0,
            'clicks': 0,
            'spend': 0.0,
            'purchases': 0.0,
            'purchase_value': 0.0
        })
        
        for row in raw_results:
            age = row.get('age', 'unknown')
            gender = row.get('gender', 'unknown')
            key = (age, gender)
            
            # Agréger les métriques de base
            segments_map[key]['impressions'] += int(row.get('impressions', 0))
            segments_map[key]['clicks'] += int(row.get('clicks', 0))
            segments_map[key]['spend'] += float(row.get('spend', 0))
            
            # Extraire purchases et purchase_value
            actions = row.get('actions', [])
            action_values = row.get('action_values', [])
            purchases, purchase_value = self._extract_purchase_data(actions, action_values)
            
            segments_map[key]['purchases'] += purchases
            segments_map[key]['purchase_value'] += purchase_value
        
        # Convertir en liste et calculer les métriques dérivées
        segments = []
        for (age, gender), metrics in segments_map.items():
            segment = {
                'age': age,
                'gender': gender,
                'impressions': metrics['impressions'],
                'clicks': metrics['clicks'],
                'spend': round(metrics['spend'], 2),
                'purchases': int(metrics['purchases']),
                'purchase_value': round(metrics['purchase_value'], 2),
                # Métriques calculées
                'ctr': round((metrics['clicks'] / metrics['impressions'] * 100) if metrics['impressions'] > 0 else 0, 2),
                'cpa': round((metrics['spend'] / metrics['purchases']) if metrics['purchases'] > 0 else 0, 2),
                'roas': round((metrics['purchase_value'] / metrics['spend']) if metrics['spend'] > 0 else 0, 2)
            }
            segments.append(segment)
        
        # Trier par spend décroissant
        segments.sort(key=lambda x: x['spend'], reverse=True)
        
        return segments
    
    def _calculate_totals(self, segments: List[Dict]) -> Dict:
        """Calcule les totaux à partir des segments"""
        totals = {
            'impressions': sum(s['impressions'] for s in segments),
            'clicks': sum(s['clicks'] for s in segments),
            'spend': round(sum(s['spend'] for s in segments), 2),
            'purchases': sum(s['purchases'] for s in segments),
            'purchase_value': round(sum(s['purchase_value'] for s in segments), 2)
        }
        
        # Calculer ROAS global
        totals['roas'] = round(
            (totals['purchase_value'] / totals['spend']) if totals['spend'] > 0 else 0, 
            2
        )
        
        return totals


def main():
    """Script principal pour fetcher les demographics de tous les comptes"""
    
    # Configuration
    TOKEN = os.getenv('META_ACCESS_TOKEN') or os.getenv('FACEBOOK_ACCESS_TOKEN')
    if not TOKEN:
        logger.error("❌ No access token found (checked META_ACCESS_TOKEN and FACEBOOK_ACCESS_TOKEN)")
        return 1
    
    DEVELOPMENT_MODE = os.getenv('DEVELOPMENT_MODE', '1') == '1'
    
    # Date de référence (hier par défaut)
    reference_date = datetime.now() - timedelta(days=1)
    
    # Périodes à fetcher - correspondent exactement aux boutons de l'UI
    PERIODS = [3, 7, 14, 30, 90]  # jours
    
    # Récupérer AUTOMATIQUEMENT tous les comptes depuis l'API (comme fetch_with_smart_limits.py)
    logger.info("📋 Récupération automatique des comptes...")
    
    import requests
    accounts_url = f"https://graph.facebook.com/v23.0/me/adaccounts"
    accounts_params = {
        "access_token": TOKEN,
        "fields": "id,name,account_status",
        "limit": 200
    }
    
    response = requests.get(accounts_url, params=accounts_params, timeout=30)
    if response.status_code != 200:
        logger.error(f"❌ Erreur récupération comptes: {response.status_code}")
        return 1
    
    all_accounts = response.json().get("data", [])
    # Filtrer les comptes actifs uniquement
    accounts = [
        {'name': acc.get('name', 'Unknown'), 'id': acc.get('id', '').replace('act_', '')}
        for acc in all_accounts 
        if acc.get("account_status") == 1
    ]
    
    if not accounts:
        logger.error("❌ No active accounts found")
        return 1
    
    logger.info(f"🚀 Starting demographics fetch for {len(accounts)} accounts")
    logger.info(f"📅 Reference date: {reference_date.strftime('%Y-%m-%d')}")
    logger.info(f"📊 Periods: {PERIODS}")
    
    # Créer le fetcher
    fetcher = DemographicsFetcher(TOKEN, DEVELOPMENT_MODE)
    
    # Créer le dossier de sortie - DANS docs/ pour GitHub Pages !
    output_base = os.getenv("DEMOGRAPHICS_OUTPUT_DIR", "docs/data/demographics")
    os.makedirs(output_base, exist_ok=True)
    
    # Stats globales
    total_success = 0
    total_failed = 0
    
    # Fetcher pour chaque compte et période
    for account in accounts:
        account_id = account['id']
        account_name = account['name']
        
        logger.info(f"\n{'='*60}")
        logger.info(f"📂 Processing {account_name} (act_{account_id})")
        
        # Créer le dossier du compte
        account_dir = os.path.join(output_base, f"act_{account_id}")
        os.makedirs(account_dir, exist_ok=True)
        
        for period_days in PERIODS:
            # Calculer les dates
            until_date = reference_date
            since_date = reference_date - timedelta(days=period_days - 1)
            
            since_str = since_date.strftime('%Y-%m-%d')
            until_str = until_date.strftime('%Y-%m-%d')
            
            try:
                # Fetcher les données
                result = fetcher.fetch_demographics_for_period(
                    account_id,
                    account_name,
                    since_str,
                    until_str,
                    period_days
                )
                
                if result:
                    # Sauvegarder le JSON
                    output_file = os.path.join(account_dir, f"{period_days}d.json")
                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump(result, f, indent=2, ensure_ascii=False)
                    
                    segments_count = len(result['segments'])
                    total_spend = result['totals']['spend']
                    logger.info(f"  ✅ {period_days}d: {segments_count} segments, ${total_spend:,.2f} spend")
                    total_success += 1
                else:
                    logger.warning(f"  ⚠️ {period_days}d: No data")
                    total_failed += 1
                    
            except Exception as e:
                logger.error(f"  ❌ {period_days}d: Error - {str(e)}")
                total_failed += 1
            
            # Pause entre périodes pour éviter rate limit
            time.sleep(2)
        
        # Pause entre comptes
        time.sleep(5)
    
    # Résumé final
    logger.info(f"\n{'='*60}")
    logger.info(f"📊 SUMMARY")
    logger.info(f"  ✅ Success: {total_success}")
    logger.info(f"  ❌ Failed: {total_failed}")
    logger.info(f"  📁 Output: {output_base}/")
    
    return 0 if total_failed == 0 else 1


if __name__ == "__main__":
    exit(main())