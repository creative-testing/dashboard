#!/usr/bin/env python3
"""
Analyseur intelligent pour Pablo - Détecte les insights cachés
"""
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import statistics

@dataclass
class CreativeInsights:
    """Insights avancés sur un créatif"""
    ad_id: str
    ad_name: str
    
    # Métriques de base (ce que Pablo demande)
    spend: float
    impressions: int
    ctr: float
    cpm: float
    roas: float
    
    # INSIGHTS CACHÉS (ce qu'il ne sait pas qu'il veut)
    
    # 1. Score de fatigue créative (0-100)
    fatigue_score: float  # Basé sur frequency + baisse CTR
    fatigue_status: str  # "Fresh", "Ok", "Fatigued", "Exhausted"
    
    # 2. Score qualité Meta (0-100)
    meta_quality_score: float  # Combine les 3 rankings de Meta
    quality_status: str  # "Excellent", "Good", "Average", "Poor"
    
    # 3. Vidéo Sweet Spot
    video_hook_strength: Optional[float]  # % qui passent 3s → 25%
    video_retention_curve: Optional[Dict[str, float]]  # 25%, 50%, 75%, 100%
    video_drop_point: Optional[str]  # Où on perd le plus ("0-25%", "25-50%", etc.)
    
    # 4. Engagement authentique
    real_engagement_rate: float  # unique_clicks / reach (pas juste clicks/impressions)
    multi_click_ratio: float  # clicks / unique_clicks (intérêt élevé si > 1.5)
    
    # 5. Funnel performance
    funnel_scores: Dict[str, float]  # view_content → add_to_cart → purchase
    biggest_drop: str  # Où on perd le plus dans le funnel
    
    # 6. Recommandations
    recommendations: List[str]  # Actions suggérées


class SmartAnalyzer:
    """Analyse intelligente des données Meta Ads"""
    
    def analyze_ad(self, ad_data: Dict[str, Any]) -> CreativeInsights:
        """
        Analyse une annonce et extrait les insights cachés
        
        Args:
            ad_data: Données brutes de l'API Meta
            
        Returns:
            CreativeInsights avec tous les insights
        """
        
        # Métriques de base
        spend = float(ad_data.get("spend", 0))
        impressions = int(ad_data.get("impressions", 0))
        reach = int(ad_data.get("reach", 0))
        clicks = int(ad_data.get("clicks", 0))
        unique_clicks = int(ad_data.get("unique_clicks", 0))
        frequency = float(ad_data.get("frequency", 1))
        ctr = float(ad_data.get("ctr", 0))
        cpm = float(ad_data.get("cpm", 0))
        
        # ROAS
        roas = self._extract_roas(ad_data)
        
        # 1. CALCUL DE LA FATIGUE CRÉATIVE
        fatigue_score, fatigue_status = self._calculate_fatigue(frequency, ctr, ad_data)
        
        # 2. SCORE QUALITÉ META
        meta_quality_score, quality_status = self._calculate_meta_quality(ad_data)
        
        # 3. ANALYSE VIDÉO (si applicable)
        video_insights = self._analyze_video_performance(ad_data)
        
        # 4. ENGAGEMENT AUTHENTIQUE
        real_engagement_rate = (unique_clicks / reach * 100) if reach > 0 else 0
        multi_click_ratio = (clicks / unique_clicks) if unique_clicks > 0 else 1
        
        # 5. ANALYSE DU FUNNEL
        funnel_scores, biggest_drop = self._analyze_funnel(ad_data)
        
        # 6. RECOMMANDATIONS INTELLIGENTES
        recommendations = self._generate_recommendations(
            fatigue_score, meta_quality_score, video_insights, 
            funnel_scores, frequency, ctr, roas
        )
        
        return CreativeInsights(
            ad_id=ad_data.get("ad_id", ""),
            ad_name=ad_data.get("ad_name", ""),
            spend=spend,
            impressions=impressions,
            ctr=ctr,
            cpm=cpm,
            roas=roas,
            fatigue_score=fatigue_score,
            fatigue_status=fatigue_status,
            meta_quality_score=meta_quality_score,
            quality_status=quality_status,
            video_hook_strength=video_insights.get("hook_strength"),
            video_retention_curve=video_insights.get("retention_curve"),
            video_drop_point=video_insights.get("drop_point"),
            real_engagement_rate=real_engagement_rate,
            multi_click_ratio=multi_click_ratio,
            funnel_scores=funnel_scores,
            biggest_drop=biggest_drop,
            recommendations=recommendations
        )
    
    def _calculate_fatigue(self, frequency: float, ctr: float, ad_data: Dict) -> tuple[float, str]:
        """
        Calcule le score de fatigue créative
        
        Logique:
        - Frequency > 3 = commence à fatiguer
        - Frequency > 5 = très fatigué
        - CTR bas + frequency haute = exhausted
        """
        fatigue_score = 0.0
        
        # Facteur frequency (0-50 points)
        if frequency <= 2:
            fatigue_score += 0
        elif frequency <= 3:
            fatigue_score += 15
        elif frequency <= 4:
            fatigue_score += 30
        elif frequency <= 5:
            fatigue_score += 40
        else:
            fatigue_score += 50
        
        # Facteur CTR (0-50 points)
        avg_ctr = 1.5  # CTR moyen Facebook
        if ctr < avg_ctr * 0.5:  # CTR très bas
            fatigue_score += 40
        elif ctr < avg_ctr * 0.75:  # CTR bas
            fatigue_score += 25
        elif ctr < avg_ctr:  # CTR sous la moyenne
            fatigue_score += 10
        
        # Déterminer le statut
        if fatigue_score < 20:
            status = "Fresh 🟢"
        elif fatigue_score < 40:
            status = "Ok 🟡"
        elif fatigue_score < 60:
            status = "Fatigued 🟠"
        else:
            status = "Exhausted 🔴"
        
        return fatigue_score, status
    
    def _calculate_meta_quality(self, ad_data: Dict) -> tuple[float, str]:
        """
        Calcule le score de qualité basé sur les rankings Meta
        """
        quality_ranking = ad_data.get("quality_ranking", "average")
        engagement_ranking = ad_data.get("engagement_rate_ranking", "average")
        conversion_ranking = ad_data.get("conversion_rate_ranking", "average")
        
        # Convertir les rankings en scores
        ranking_scores = {
            "above_average": 100,
            "average": 50,
            "below_average": 25,
            "below_average_10": 10,
            "below_average_20": 5,
            "below_average_35": 0
        }
        
        scores = []
        for ranking in [quality_ranking, engagement_ranking, conversion_ranking]:
            if ranking and ranking in ranking_scores:
                scores.append(ranking_scores[ranking])
            else:
                scores.append(50)  # Default to average
        
        # Score moyen
        meta_score = statistics.mean(scores) if scores else 50
        
        # Statut
        if meta_score >= 75:
            status = "Excellent ⭐"
        elif meta_score >= 50:
            status = "Good ✅"
        elif meta_score >= 25:
            status = "Average ⚠️"
        else:
            status = "Poor ❌"
        
        return meta_score, status
    
    def _analyze_video_performance(self, ad_data: Dict) -> Dict:
        """
        Analyse la performance vidéo avec les points de chute
        """
        video_insights = {}
        
        # Extraire les métriques vidéo
        video_plays = self._extract_video_metric(ad_data, "video_play_actions")
        video_p25 = self._extract_video_metric(ad_data, "video_p25_watched_actions")
        video_p50 = self._extract_video_metric(ad_data, "video_p50_watched_actions")
        video_p75 = self._extract_video_metric(ad_data, "video_p75_watched_actions")
        video_p100 = self._extract_video_metric(ad_data, "video_p100_watched_actions")
        
        if video_plays and video_plays > 0:
            # Calculer la force du hook (3s → 25%)
            if video_p25:
                video_insights["hook_strength"] = (video_p25 / video_plays) * 100
            
            # Courbe de rétention
            video_insights["retention_curve"] = {
                "0%": 100,
                "3s": 100,
                "25%": (video_p25 / video_plays * 100) if video_p25 else 0,
                "50%": (video_p50 / video_plays * 100) if video_p50 else 0,
                "75%": (video_p75 / video_plays * 100) if video_p75 else 0,
                "100%": (video_p100 / video_plays * 100) if video_p100 else 0
            }
            
            # Identifier le plus gros point de chute
            drops = []
            if video_p25:
                drops.append(("0-25%", 100 - (video_p25/video_plays*100)))
            if video_p25 and video_p50:
                drops.append(("25-50%", (video_p25-video_p50)/video_plays*100))
            if video_p50 and video_p75:
                drops.append(("50-75%", (video_p50-video_p75)/video_plays*100))
            if video_p75 and video_p100:
                drops.append(("75-100%", (video_p75-video_p100)/video_plays*100))
            
            if drops:
                biggest_drop = max(drops, key=lambda x: x[1])
                video_insights["drop_point"] = f"{biggest_drop[0]} (-{biggest_drop[1]:.1f}%)"
        
        return video_insights
    
    def _analyze_funnel(self, ad_data: Dict) -> tuple[Dict[str, float], str]:
        """
        Analyse le funnel de conversion
        """
        funnel_scores = {}
        actions = ad_data.get("actions", [])
        
        # Extraire les métriques du funnel
        metrics = {}
        for action in actions:
            action_type = action.get("action_type")
            value = float(action.get("value", 0))
            
            if action_type in ["view_content", "add_to_cart", "purchase", "initiate_checkout"]:
                metrics[action_type] = value
        
        # Calculer les taux de conversion entre étapes
        impressions = int(ad_data.get("impressions", 1))
        
        if "view_content" in metrics and impressions > 0:
            funnel_scores["impression_to_view"] = (metrics["view_content"] / impressions) * 100
        
        if "view_content" in metrics and "add_to_cart" in metrics and metrics["view_content"] > 0:
            funnel_scores["view_to_cart"] = (metrics["add_to_cart"] / metrics["view_content"]) * 100
        
        if "add_to_cart" in metrics and "purchase" in metrics and metrics["add_to_cart"] > 0:
            funnel_scores["cart_to_purchase"] = (metrics["purchase"] / metrics["add_to_cart"]) * 100
        
        # Identifier la plus grosse chute
        biggest_drop = "N/A"
        if funnel_scores:
            min_score = min(funnel_scores.items(), key=lambda x: x[1])
            biggest_drop = f"{min_score[0]} ({min_score[1]:.1f}%)"
        
        return funnel_scores, biggest_drop
    
    def _extract_roas(self, ad_data: Dict) -> float:
        """Extrait le ROAS des données"""
        roas_data = ad_data.get("purchase_roas", [])
        if roas_data and isinstance(roas_data, list) and len(roas_data) > 0:
            return float(roas_data[0].get("value", 0))
        return 0.0
    
    def _extract_video_metric(self, ad_data: Dict, metric_name: str) -> Optional[int]:
        """Extrait une métrique vidéo spécifique"""
        metric_data = ad_data.get(metric_name, [])
        if metric_data and isinstance(metric_data, list) and len(metric_data) > 0:
            for item in metric_data:
                if item.get("action_type") == "video_view":
                    return int(item.get("value", 0))
        return None
    
    def _generate_recommendations(self, fatigue_score: float, meta_quality: float, 
                                 video_insights: Dict, funnel_scores: Dict,
                                 frequency: float, ctr: float, roas: float) -> List[str]:
        """
        Génère des recommandations intelligentes basées sur l'analyse
        """
        recommendations = []
        
        # Fatigue créative
        if fatigue_score > 60:
            recommendations.append("🔄 URGENT: Rafraîchir le créatif (fatigue élevée)")
        elif fatigue_score > 40:
            recommendations.append("⚠️ Préparer nouveau créatif (fatigue modérée)")
        
        # Qualité Meta
        if meta_quality < 25:
            recommendations.append("❌ Améliorer qualité: texte, image ou ciblage")
        elif meta_quality < 50:
            recommendations.append("📈 Optimiser pour meilleur engagement")
        
        # Vidéo
        if video_insights.get("hook_strength") and video_insights["hook_strength"] < 50:
            recommendations.append("🎬 Renforcer les 3 premières secondes (hook faible)")
        
        if video_insights.get("drop_point"):
            drop = video_insights["drop_point"]
            if "0-25%" in drop:
                recommendations.append("⏰ Message principal trop tardif")
            elif "25-50%" in drop:
                recommendations.append("📝 Simplifier le message du milieu")
        
        # Funnel
        if funnel_scores:
            worst_step = min(funnel_scores.items(), key=lambda x: x[1]) if funnel_scores else None
            if worst_step and worst_step[1] < 2:
                if "view_to_cart" in worst_step[0]:
                    recommendations.append("🛒 Améliorer l'incitation à l'ajout au panier")
                elif "cart_to_purchase" in worst_step[0]:
                    recommendations.append("💳 Réduire les frictions au checkout")
        
        # ROAS
        if roas < 1.5:
            recommendations.append("💰 ROAS faible: revoir ciblage ou offre")
        elif roas > 3:
            recommendations.append("🚀 Scaler cette annonce (ROAS excellent)")
        
        # Frequency
        if frequency > 5:
            recommendations.append("🎯 Élargir l'audience (frequency trop élevée)")
        
        return recommendations if recommendations else ["✅ Performance correcte, continuer le test"]


def demo_analysis():
    """Démo de l'analyseur intelligent"""
    
    # Exemple de données d'une annonce
    sample_ad = {
        "ad_id": "123456",
        "ad_name": "Video_Inflammation_Carlos25",
        "spend": "5000",
        "impressions": "25000",
        "reach": "15000", 
        "clicks": "500",
        "unique_clicks": "350",
        "frequency": "3.5",
        "ctr": "2.0",
        "cpm": "200",
        "purchase_roas": [{"value": "2.5"}],
        "quality_ranking": "average",
        "engagement_rate_ranking": "above_average",
        "conversion_rate_ranking": "average",
        "video_play_actions": [{"action_type": "video_view", "value": "10000"}],
        "video_p25_watched_actions": [{"action_type": "video_view", "value": "6000"}],
        "video_p50_watched_actions": [{"action_type": "video_view", "value": "3000"}],
        "video_p75_watched_actions": [{"action_type": "video_view", "value": "1500"}],
        "video_p100_watched_actions": [{"action_type": "video_view", "value": "500"}],
        "actions": [
            {"action_type": "view_content", "value": "2000"},
            {"action_type": "add_to_cart", "value": "200"},
            {"action_type": "purchase", "value": "50"}
        ]
    }
    
    analyzer = SmartAnalyzer()
    insights = analyzer.analyze_ad(sample_ad)
    
    print("🧠 ANALYSE INTELLIGENTE DE L'ANNONCE")
    print("=" * 60)
    print(f"Annonce: {insights.ad_name}")
    print(f"Dépense: ${insights.spend:.2f} | ROAS: {insights.roas:.2f}")
    print()
    print("📊 INSIGHTS CACHÉS:")
    print(f"  • Fatigue créative: {insights.fatigue_status} ({insights.fatigue_score:.0f}/100)")
    print(f"  • Qualité Meta: {insights.quality_status} ({insights.meta_quality_score:.0f}/100)")
    print(f"  • Engagement réel: {insights.real_engagement_rate:.2f}%")
    print(f"  • Multi-clics ratio: {insights.multi_click_ratio:.2f}x")
    
    if insights.video_retention_curve:
        print("\n🎥 ANALYSE VIDÉO:")
        print(f"  • Force du hook: {insights.video_hook_strength:.1f}%")
        print(f"  • Point de chute: {insights.video_drop_point}")
        print("  • Courbe de rétention:")
        for point, value in insights.video_retention_curve.items():
            print(f"    {point}: {value:.1f}%")
    
    if insights.funnel_scores:
        print("\n🔄 FUNNEL:")
        for step, score in insights.funnel_scores.items():
            print(f"  • {step}: {score:.2f}%")
        print(f"  • Biggest drop: {insights.biggest_drop}")
    
    print("\n💡 RECOMMANDATIONS:")
    for rec in insights.recommendations:
        print(f"  {rec}")


if __name__ == "__main__":
    demo_analysis()