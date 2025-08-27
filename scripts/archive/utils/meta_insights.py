"""
Module d'ingestion des données Meta Ads via l'API Graph
Utilise l'approche "Insights-first" pour récupérer toutes les métriques
"""
import json
import requests
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging
from config import MetaConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MetaInsightsFetcher:
    """Récupère les données des publicités Meta via l'API Graph Insights"""
    
    def __init__(self, access_token: str = None, account_id: str = None):
        self.access_token = access_token or MetaConfig.ACCESS_TOKEN
        self.account_id = account_id or MetaConfig.ACCOUNT_ID
        
        if not self.access_token:
            raise ValueError("META_ACCESS_TOKEN manquant. Configurez-le dans .env")
        
        if not self.account_id:
            raise ValueError("META_ACCOUNT_ID manquant. Configurez-le dans .env")
        
        # Nettoyer l'account_id
        if not self.account_id.startswith("act_"):
            self.account_id = f"act_{self.account_id}"
    
    def fetch_insights(
        self,
        lookback_days: int = 7,
        level: str = "ad",
        filtering: Optional[List[Dict]] = None,
        sort: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Récupère les insights Meta Ads via l'API Graph
        
        Args:
            lookback_days: Nombre de jours en arrière
            level: Niveau d'agrégation (ad, adset, campaign)
            filtering: Filtres API (ex: [{"field": "ad.effective_status", "operator": "EQUAL", "value": "ACTIVE"}])
            sort: Tri côté serveur (ex: "spend_descending")
            limit: Nombre de résultats par page
        
        Returns:
            Liste des insights pour toutes les publicités
        """
        url = f"{MetaConfig.BASE_URL}/{self.account_id}/insights"
        
        # Construire les paramètres
        params = {
            "access_token": self.access_token,
            "level": level,
            "date_preset": f"last_{lookback_days}d" if lookback_days <= 90 else "last_90d",
            "fields": ",".join(MetaConfig.INSIGHTS_FIELDS),
            "limit": limit
        }
        
        # Note: effective_status n'est pas supporté dans l'API Insights
        # On récupère tout et on filtrera après si nécessaire
        if filtering and filtering != "no_filter":
            params["filtering"] = json.dumps(filtering)
        
        if sort:
            params["sort"] = sort
        
        # Récupérer toutes les pages
        all_insights = []
        next_page = url
        page_count = 0
        
        logger.info(f"Début de la récupération des insights pour {self.account_id}")
        logger.info(f"Période: {lookback_days} derniers jours, Niveau: {level}")
        
        while next_page and page_count < 50:  # Limite de sécurité
            try:
                response = requests.get(next_page, params=params if page_count == 0 else None)
                response.raise_for_status()
                data = response.json()
                
                insights = data.get("data", [])
                all_insights.extend(insights)
                
                logger.info(f"Page {page_count + 1}: {len(insights)} résultats récupérés")
                
                # Pagination
                paging = data.get("paging", {})
                next_page = paging.get("next")
                page_count += 1
                
                # Reset params après la première page (ils sont dans l'URL next)
                params = None
                
            except requests.RequestException as e:
                logger.error(f"Erreur API Meta: {e}")
                if hasattr(e.response, 'text'):
                    logger.error(f"Réponse: {e.response.text}")
                break
        
        logger.info(f"Total: {len(all_insights)} insights récupérés")
        return all_insights
    
    def process_insights(self, insights: List[Dict]) -> List[Dict]:
        """
        Traite et enrichit les insights bruts
        
        Args:
            insights: Liste des insights bruts de l'API
        
        Returns:
            Liste des insights enrichis avec métriques calculées
        """
        processed = []
        
        for insight in insights:
            # Copier les données de base
            ad_data = {
                "ad_id": insight.get("ad_id"),
                "ad_name": insight.get("ad_name"),
                "campaign_id": insight.get("campaign_id"),
                "campaign_name": insight.get("campaign_name"),
                "adset_id": insight.get("adset_id"),
                "adset_name": insight.get("adset_name"),
                "spend": float(insight.get("spend", 0)),
                "impressions": int(insight.get("impressions", 0)),
                "reach": int(insight.get("reach", 0)),
                "frequency": float(insight.get("frequency", 0)),
                "clicks": int(insight.get("clicks", 0)),
                "unique_clicks": int(insight.get("unique_clicks", 0)),
                "ctr": float(insight.get("ctr", 0)),
                "unique_ctr": float(insight.get("unique_ctr", 0)),
                "cpm": float(insight.get("cpm", 0)),
                "cpc": float(insight.get("cpc", 0)),
            }
            
            # Extraire les conversions et valeurs
            actions = insight.get("actions", [])
            action_values = insight.get("action_values", [])
            cost_per_action = insight.get("cost_per_action_type", [])
            
            # Chercher les achats
            purchases = 0
            purchase_value = 0.0
            cpa = 0.0
            
            for action in actions:
                if action.get("action_type") in ["purchase", "omni_purchase"]:
                    purchases = int(action.get("value", 0))
                    break
            
            for value in action_values:
                if value.get("action_type") in ["purchase", "omni_purchase"]:
                    purchase_value = float(value.get("value", 0))
                    break
            
            for cost in cost_per_action:
                if cost.get("action_type") in ["purchase", "omni_purchase"]:
                    cpa = float(cost.get("value", 0))
                    break
            
            ad_data["purchases"] = purchases
            ad_data["purchase_value"] = purchase_value
            ad_data["cpa"] = cpa
            
            # ROAS (Return on Ad Spend)
            roas_data = insight.get("purchase_roas", [])
            if roas_data and isinstance(roas_data, list) and len(roas_data) > 0:
                ad_data["roas"] = float(roas_data[0].get("value", 0))
            else:
                # Calculer manuellement si pas fourni
                ad_data["roas"] = purchase_value / ad_data["spend"] if ad_data["spend"] > 0 else 0
            
            # Métriques vidéo (pour Hook Rate et Hold Rate)
            video_3s = 0
            video_complete = 0
            
            video_play_actions = insight.get("video_play_actions", [])
            for action in video_play_actions:
                if action.get("action_type") == "video_view":
                    video_3s = int(action.get("value", 0))
                    break
            
            video_p100 = insight.get("video_p100_watched_actions", [])
            for action in video_p100:
                if action.get("action_type") == "video_view":
                    video_complete = int(action.get("value", 0))
                    break
            
            # Calculer Hook Rate et Hold Rate si c'est une vidéo
            if video_3s > 0:
                ad_data["video_3s_views"] = video_3s
                ad_data["video_complete_views"] = video_complete
                ad_data["hook_rate"] = (video_3s / ad_data["impressions"] * 100) if ad_data["impressions"] > 0 else 0
                ad_data["hold_rate"] = (video_complete / video_3s * 100) if video_3s > 0 else 0
            else:
                ad_data["video_3s_views"] = None
                ad_data["video_complete_views"] = None
                ad_data["hook_rate"] = None
                ad_data["hold_rate"] = None
            
            # Ajouter la date de récupération
            ad_data["fetched_at"] = datetime.now().isoformat()
            
            processed.append(ad_data)
        
        return processed
    
    def fetch_creative_details(self, ad_ids: List[str]) -> Dict[str, Dict]:
        """
        Récupère les détails des créatifs pour une liste d'annonces
        
        Args:
            ad_ids: Liste des IDs d'annonces
        
        Returns:
            Dictionnaire {ad_id: creative_info}
        """
        creative_map = {}
        
        # Traiter par batch de 50
        for i in range(0, len(ad_ids), 50):
            batch = ad_ids[i:i+50]
            ids = ",".join(batch)
            
            url = f"{MetaConfig.BASE_URL}/"
            params = {
                "ids": ids,
                "fields": "id,creative{thumbnail_url,object_story_spec,title,body,image_url,video_id}",
                "access_token": self.access_token
            }
            
            try:
                response = requests.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                
                for ad_id, ad_info in data.items():
                    if "creative" in ad_info:
                        creative = ad_info["creative"]
                        creative_map[ad_id] = {
                            "thumbnail_url": creative.get("thumbnail_url"),
                            "title": creative.get("title"),
                            "body": creative.get("body"),
                            "image_url": creative.get("image_url"),
                            "video_id": creative.get("video_id"),
                        }
                
                logger.info(f"Récupéré {len(creative_map)} créatifs sur {len(batch)} annonces")
                
            except requests.RequestException as e:
                logger.error(f"Erreur lors de la récupération des créatifs: {e}")
        
        return creative_map


def test_connection():
    """Teste la connexion à l'API Meta"""
    try:
        fetcher = MetaInsightsFetcher()
        
        # Test simple : récupérer 5 insights sans filtre
        insights = fetcher.fetch_insights(lookback_days=7, limit=5, filtering="no_filter")
        
        if insights:
            print(f"✅ Connexion réussie ! {len(insights)} annonces trouvées.")
            print(f"Exemple d'annonce: {insights[0].get('ad_name', 'N/A')}")
            
            # Traiter les insights
            processed = fetcher.process_insights(insights)
            print(f"\n📊 Métriques de la première annonce:")
            for key, value in processed[0].items():
                if value is not None:
                    print(f"  {key}: {value}")
        else:
            print("⚠️ Aucune annonce trouvée. Vérifiez que le compte a des pubs actives.")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur de connexion: {e}")
        return False


if __name__ == "__main__":
    test_connection()