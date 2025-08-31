#!/usr/bin/env python3
"""
Gestionnaire intelligent de rate limiting pour l'API Meta Ads
Basé sur les recommandations des assistants de recherche
"""
import json
import time
import logging
from typing import Dict, Optional
import random

logger = logging.getLogger(__name__)

class RateLimitManager:
    """Gère proactivement les rate limits de l'API Meta"""
    
    def __init__(self, development_mode=True):
        self.development_mode = development_mode
        # Limites selon le tier
        self.max_score = 60 if development_mode else 9000
        self.decay_time = 300 if development_mode else 60  # secondes
        
        # Tracking par compte
        self.account_usage = {}
        self.last_check_time = {}
        
    def parse_headers(self, headers: dict, account_id: str) -> Dict:
        """Parse les headers de rate limit de Meta"""
        usage_info = {
            'should_pause': False,
            'pause_duration': 0,
            'usage_percent': 0,
            'details': {}
        }
        
        # X-Business-Use-Case-Usage (le plus détaillé)
        if 'x-business-use-case-usage' in headers:
            try:
                buc_data = json.loads(headers['x-business-use-case-usage'])
                
                # Chercher notre account_id dans les données
                for acc_key, usages in buc_data.items():
                    if account_id in acc_key or acc_key == account_id:
                        for usage in usages:
                            # Récupérer les métriques
                            call_count = usage.get('call_count', 0)
                            total_time = usage.get('total_time', 0)
                            total_cputime = usage.get('total_cputime', 0)
                            estimated_time = usage.get('estimated_time_to_regain_access', 0)
                            
                            # Prendre le max des métriques
                            max_usage = max(call_count, total_time, total_cputime)
                            usage_info['usage_percent'] = max(usage_info['usage_percent'], max_usage)
                            
                            # Si on a un temps d'attente estimé
                            if estimated_time > 0:
                                usage_info['pause_duration'] = estimated_time * 60  # Convert to seconds
                                usage_info['should_pause'] = True
                            
                            usage_info['details'][usage.get('type', 'unknown')] = {
                                'calls': call_count,
                                'time': total_time,
                                'cpu': total_cputime
                            }
                            
                            logger.info(f"  📊 {account_id} - {usage.get('type')}: "
                                      f"Calls={call_count}%, Time={total_time}%, CPU={total_cputime}%")
            except Exception as e:
                logger.warning(f"Erreur parsing BUC headers: {e}")
        
        # X-Ad-Account-Usage (fallback plus simple)
        elif 'x-ad-account-usage' in headers:
            try:
                usage_data = json.loads(headers['x-ad-account-usage'])
                usage_percent = usage_data.get('acc_id_util_pct', 0)
                usage_info['usage_percent'] = usage_percent
                
                logger.info(f"  📊 {account_id} - Usage: {usage_percent}%")
                
                # Temps de reset si disponible
                if 'reset_time_duration' in usage_data:
                    usage_info['pause_duration'] = usage_data['reset_time_duration']
            except Exception as e:
                logger.warning(f"Erreur parsing account headers: {e}")
        
        # X-FB-Ads-Insights-Throttle (spécifique insights)
        if 'x-fb-ads-insights-throttle' in headers:
            try:
                throttle_data = json.loads(headers['x-fb-ads-insights-throttle'])
                app_usage = throttle_data.get('app_id_util_pct', 0)
                acc_usage = throttle_data.get('acc_id_util_pct', 0)
                
                max_insights = max(app_usage, acc_usage)
                usage_info['usage_percent'] = max(usage_info['usage_percent'], max_insights)
                
                logger.info(f"  📊 Insights - App: {app_usage}%, Account: {acc_usage}%")
            except Exception as e:
                logger.warning(f"Erreur parsing insights headers: {e}")
        
        # Décision de pause proactive
        if self.development_mode:
            # En dev, on est très conservateur
            if usage_info['usage_percent'] >= 75:
                usage_info['should_pause'] = True
                if usage_info['pause_duration'] == 0:
                    # Pause proportionnelle à l'usage
                    if usage_info['usage_percent'] >= 90:
                        usage_info['pause_duration'] = 120  # 2 minutes
                    else:
                        usage_info['pause_duration'] = 60   # 1 minute
        else:
            # En production, seuil plus haut
            if usage_info['usage_percent'] >= 90:
                usage_info['should_pause'] = True
                if usage_info['pause_duration'] == 0:
                    usage_info['pause_duration'] = 30  # 30 secondes
        
        # Stocker pour tracking
        self.account_usage[account_id] = usage_info
        self.last_check_time[account_id] = time.time()
        
        return usage_info
    
    def should_pause(self, account_id: str) -> tuple[bool, int]:
        """Vérifie si on doit faire une pause pour ce compte"""
        if account_id not in self.account_usage:
            return False, 0
        
        usage = self.account_usage[account_id]
        return usage['should_pause'], usage['pause_duration']
    
    def apply_smart_delay(self, account_id: str, headers: dict):
        """Applique un délai intelligent basé sur les headers"""
        usage_info = self.parse_headers(headers, account_id)
        
        if usage_info['should_pause']:
            pause_time = usage_info['pause_duration']
            # Ajouter du jitter (±10%) pour éviter le thundering herd
            jitter = random.uniform(0.9, 1.1)
            pause_time = int(pause_time * jitter)
            
            logger.info(f"  ⏸️  Pause proactive de {pause_time}s pour {account_id} "
                       f"(usage: {usage_info['usage_percent']}%)")
            time.sleep(pause_time)
    
    def get_optimal_batch_size(self, account_id: str) -> int:
        """Détermine la taille optimale de batch selon l'usage"""
        if account_id not in self.account_usage:
            return 50 if not self.development_mode else 25
        
        usage_percent = self.account_usage[account_id]['usage_percent']
        
        if self.development_mode:
            # En dev, on réduit progressivement
            if usage_percent < 50:
                return 25
            elif usage_percent < 75:
                return 10
            else:
                return 5
        else:
            # En production
            if usage_percent < 70:
                return 50
            elif usage_percent < 85:
                return 25
            else:
                return 10
    
    def get_worker_count(self) -> int:
        """Détermine le nombre optimal de workers"""
        if self.development_mode:
            # En dev, très conservateur
            avg_usage = sum(u['usage_percent'] for u in self.account_usage.values()) / max(len(self.account_usage), 1)
            if avg_usage > 70:
                return 2
            elif avg_usage > 50:
                return 4
            else:
                return 8
        else:
            # En production, plus agressif
            return 32
    
    def log_summary(self):
        """Affiche un résumé de l'état des rate limits"""
        if not self.account_usage:
            return
        
        logger.info("\n📊 === Résumé Rate Limits ===")
        high_usage = []
        for acc_id, usage in self.account_usage.items():
            if usage['usage_percent'] > 70:
                high_usage.append(f"{acc_id}: {usage['usage_percent']}%")
        
        if high_usage:
            logger.warning(f"⚠️ Comptes à usage élevé: {', '.join(high_usage)}")
        
        avg_usage = sum(u['usage_percent'] for u in self.account_usage.values()) / len(self.account_usage)
        logger.info(f"📈 Usage moyen: {avg_usage:.1f}%")
        logger.info(f"👷 Workers recommandés: {self.get_worker_count()}")