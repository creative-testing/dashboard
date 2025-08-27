"""
Configuration centralisée pour l'agent Creative Testing
"""
import os
from typing import Dict, List, Optional
from dataclasses import dataclass
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

@dataclass
class BrandConfig:
    """Configuration spécifique par marque/client"""
    brand_id: str
    account_ids: List[str]
    
    # Seuils pour classification gagnant/perdant
    min_spend: float = 5000.0
    min_roas: Optional[float] = 2.5
    min_ctr: Optional[float] = None  # Alternative à ROAS
    
    # Dictionnaires de parsing
    angle_keywords: Dict[str, List[str]] = None
    format_keywords: Dict[str, List[str]] = None
    creator_patterns: Dict[str, str] = None
    
    def __post_init__(self):
        if self.angle_keywords is None:
            self.angle_keywords = {
                "inflamacion": ["inflamación", "inflamma", "bloating", "hinchazón"],
                "digestion": ["digestión", "digestion", "gut", "intestinal"],
                "energia": ["energía", "energy", "vitalidad", "fatiga"],
                "inmunidad": ["inmunidad", "immunity", "defensas", "immune"],
                "piel": ["piel", "skin", "dermis", "cutáneo"],
            }
        
        if self.format_keywords is None:
            self.format_keywords = {
                "video": ["video", "vid", "reel", "mp4"],
                "image": ["img", "image", "imagen", "jpg", "png", "static"],
                "carousel": ["carousel", "carrusel", "multi"],
            }
        
        if self.creator_patterns is None:
            # Patterns regex pour détecter créateur + âge
            self.creator_patterns = {
                "male_age": r"(?:Hombre|Homme|Man|M|H)[\s_-]?(\d{2})",
                "female_age": r"(?:Mujer|Femme|Woman|F|W)[\s_-]?(\d{2})",
                "name_age": r"([A-Z][a-z]+)[\s_-]?(\d{2})",  # Carlos25, Ana_30
            }


class MetaConfig:
    """Configuration pour l'API Meta/Facebook"""
    ACCESS_TOKEN = os.getenv("FACEBOOK_ACCESS_TOKEN")
    ACCOUNT_ID = os.getenv("META_ACCOUNT_ID", "").replace("act_", "")  # Nettoyer le préfixe si présent
    API_VERSION = os.getenv("API_VERSION", "v23.0")
    BASE_URL = f"https://graph.facebook.com/{API_VERSION}"
    
    # Champs INTELLIGENTS pour Pablo - Ce qu'il demande + Ce qu'il ne sait pas qu'il veut
    INSIGHTS_FIELDS = [
        # === ESSENTIELS (ce que Pablo demande) ===
        "ad_id",
        "ad_name", 
        "campaign_id",
        "campaign_name",
        "adset_id",
        "adset_name",
        
        # Métriques de base pour son tableau
        "spend",  # Importe Gastado
        "impressions",
        "reach",
        "clicks",
        "ctr",  # CTR
        "cpm",  # CPM
        "purchase_roas",  # ROAS principal
        
        # === CE QU'IL NE SAIT PAS QU'IL VEUT ===
        
        # 1. QUALITÉ & RANKING (Meta nous dit si c'est bon)
        "quality_ranking",  # ⭐ Qualité vs autres annonces
        "engagement_rate_ranking",  # ⭐ Engagement vs concurrents
        "conversion_rate_ranking",  # ⭐ Conversion vs concurrents
        
        # 2. VIDÉO INTELLIGENCE (voir où on perd l'audience)
        "video_play_actions",  # Démarrages vidéo (3s)
        "video_p25_watched_actions",  # 🎬 25% vus (Hook validé)
        "video_p50_watched_actions",  # 🎬 50% vus (Message passé)
        "video_p75_watched_actions",  # 🎬 75% vus (Très engagés)
        "video_p100_watched_actions",  # 🎬 100% vus (Super fans)
        "video_avg_time_watched_actions",  # ⏱️ Temps moyen
        "video_thruplay_watched_actions",  # Vues complètes ou 15s+
        
        # 3. FATIGUE CRÉATIVE & ENGAGEMENT
        "frequency",  # 🔄 Combien de fois la même personne voit l'annonce
        "unique_clicks",  # 👆 Vrais clics uniques (pas les multi-cliqueurs)
        "unique_ctr",  # CTR unique (plus précis)
        "inline_link_clicks",  # Clics dans Facebook (vs sortie)
        "outbound_clicks",  # Vrais clics sortants
        
        # 4. FUNNEL COMPLET (voir où on perd)
        "actions",  # TOUTES les actions (view_content, add_to_cart, purchase...)
        "action_values",  # Valeur de chaque action
        "cost_per_action_type",  # CPA par type d'action
        
        # 5. PRÉDICTIONS META
        "estimated_ad_recall_rate",  # 🧠 % qui se souviendront
        "estimated_ad_recallers",  # Nombre estimé qui se souviendront
        
        # 6. DONNÉES TEMPORELLES
        "date_start",
        "date_stop",
        
        # 7. OPTIMISATION & OBJECTIFS
        "objective",  # Objectif de campagne
        "optimization_goal",  # Sur quoi on optimise
        
        # 8. COÛTS DÉTAILLÉS
        "cpc",  # Coût par clic
        "cpp",  # Coût par 1000 personnes atteintes
        "cost_per_thruplay",  # Coût par vue complète vidéo
        
        # 9. ATTRIBUTION
        "attribution_setting",  # Fenêtre d'attribution utilisée
    ]
    
    # Champs supplémentaires pour récupérer les CRÉATIFS (via autre endpoint)
    CREATIVE_FIELDS = [
        "id",
        "name", 
        "title",  # Titre de l'annonce
        "body",  # Texte principal
        "call_to_action_type",  # Type de CTA (SHOP_NOW, LEARN_MORE...)
        "image_url",  # URL de l'image
        "image_hash",  # Hash pour identifier l'image
        "video_id",  # ID de la vidéo
        "thumbnail_url",  # Miniature
        "link_url",  # URL de destination
        "instagram_permalink_url",  # Post Instagram associé
    ]
    
    # Breakdowns disponibles pour segmentation
    AVAILABLE_BREAKDOWNS = [
        "age",  # Performance par âge
        "gender",  # Homme vs Femme
        "publisher_platform",  # Facebook vs Instagram
        "impression_device",  # Mobile vs Desktop
        "hourly_stats_aggregated_by_advertiser_time_zone",  # Par heure
        "country",  # Par pays
    ]
    
    # Période par défaut
    DEFAULT_LOOKBACK_DAYS = int(os.getenv("DEFAULT_LOOKBACK_DAYS", "7"))
    
    @classmethod
    def get_insights_url(cls, account_id: str = None) -> str:
        """Construit l'URL pour l'endpoint Insights"""
        acc_id = account_id or cls.ACCOUNT_ID
        if not acc_id.startswith("act_"):
            acc_id = f"act_{acc_id}"
        return f"{cls.BASE_URL}/{acc_id}/insights"


class GoogleSheetsConfig:
    """Configuration pour Google Sheets"""
    SHEET_ID = os.getenv("GOOGLE_SHEETS_ID")
    CREDENTIALS_PATH = os.getenv("GOOGLE_SHEETS_CREDENTIALS_JSON", "credentials.json")
    
    # Noms des onglets
    TABS = {
        "config": "Config",
        "raw": "Raw_Ads",
        "parsed": "Parsed_Entities",
        "aggregates": "Aggregates",
        "summary": "Summary",
        "charts": "Charts",
        "quality": "Quality_Report"
    }


class ParsingConfig:
    """Configuration pour le parsing des noms d'annonces"""
    # Schéma officiel de nomenclature
    OFFICIAL_SCHEMA = r"^(?P<angle>[^|]+)\|(?P<creator>[^|]+)\|(?P<format>[^|]+)$"
    
    # Activer LLM pour cas ambigus
    ENABLE_LLM = os.getenv("ENABLE_LLM_PARSING", "false").lower() == "true"
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    
    # Seuil de confiance pour LLM
    LLM_CONFIDENCE_THRESHOLD = 0.7
    
    # Prompt LLM pour parsing
    LLM_PROMPT = """
    Analyze this Facebook ad name and extract:
    1. Marketing angle (inflamacion, digestion, energia, etc.)
    2. Creator info (gender and age if present)
    3. Format type (video, image, carousel)
    
    Ad name: {ad_name}
    
    Return JSON only:
    {
        "angle": "...",
        "creator_gender": "M/F/unknown",
        "creator_age": number or null,
        "format": "video/image/carousel/unknown",
        "confidence": 0.0-1.0
    }
    """


# Instance par défaut pour une marque
default_brand_config = BrandConfig(
    brand_id="default",
    account_ids=[MetaConfig.ACCOUNT_ID] if MetaConfig.ACCOUNT_ID else []
)
