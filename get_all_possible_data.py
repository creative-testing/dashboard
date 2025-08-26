#!/usr/bin/env python3
"""
Script pour récupérer TOUTES les données possibles des annonces des 7 derniers jours
"""
import requests
import json
from datetime import datetime
from dotenv import load_dotenv
import os

load_dotenv()

def get_all_possible_fields():
    """Récupère TOUTES les données possibles pour les 7 derniers jours"""
    
    token = os.getenv("FB_TOKEN")
    account_id = "act_297112083495970"
    
    print("🔍 RÉCUPÉRATION DE TOUTES LES DONNÉES POSSIBLES (7 DERNIERS JOURS)")
    print("=" * 80)
    
    # 1. D'ABORD, TESTER TOUS LES CHAMPS INSIGHTS POSSIBLES
    print("\n📊 TEST DES CHAMPS DISPONIBLES DANS INSIGHTS...")
    
    # Liste complète des champs possibles pour Insights
    all_fields = [
        # === IDENTIFIANTS ===
        "ad_id", "ad_name", "campaign_id", "campaign_name",
        "adset_id", "adset_name", "account_id", "account_name",
        "account_currency", "campaign_budget_optimization",
        
        # === DATES ET TEMPS ===
        "date_start", "date_stop", "created_time", "updated_time",
        
        # === MÉTRIQUES DE BASE ===
        "impressions", "reach", "frequency", "spend",
        "objective", "optimization_goal", "buying_type",
        "bid_strategy", "daily_budget", "lifetime_budget",
        
        # === TOUS LES TYPES DE CLICS ===
        "clicks", "unique_clicks", "all_clicks",
        "link_clicks", "unique_link_clicks",
        "outbound_clicks", "unique_outbound_clicks",
        "inline_link_clicks", "unique_inline_link_clicks",
        "social_clicks", "unique_social_clicks",
        "website_clicks", "button_clicks",
        "call_to_action_clicks", "deeplink_clicks",
        "contact_actions", "get_directions_actions",
        
        # === TAUX ET COÛTS ===
        "ctr", "unique_ctr", "inline_link_click_ctr", "outbound_clicks_ctr",
        "cpm", "cpp", "cpc", "cost_per_unique_click",
        "cost_per_inline_link_click", "cost_per_unique_inline_link_click",
        "cost_per_outbound_click", "cost_per_unique_outbound_click",
        
        # === ACTIONS ET CONVERSIONS (TOUS TYPES) ===
        "actions", "action_values", "conversions", "conversion_values",
        "cost_per_action_type", "cost_per_conversion",
        "cost_per_unique_action_type", "unique_actions",
        "website_conversions", "website_conversion_values",
        "mobile_app_conversions", "mobile_app_conversion_values",
        "onsite_conversions", "catalog_segment_actions",
        "catalog_segment_value", "catalog_segment_value_mobile_purchase_roas",
        "catalog_segment_value_omni_purchase_roas",
        "catalog_segment_value_website_purchase_roas",
        
        # === ROAS (TOUS TYPES) ===
        "purchase_roas", "website_purchase_roas", 
        "mobile_app_purchase_roas", "omni_purchase_roas",
        
        # === VIDÉO - TOUTES LES MÉTRIQUES ===
        "video_play_actions", "video_play_curve_actions",
        "video_avg_time_watched_actions", "video_time_watched_actions",
        "video_p25_watched_actions", "video_p50_watched_actions",
        "video_p75_watched_actions", "video_p95_watched_actions",
        "video_p100_watched_actions",
        "video_15s_watched_actions", "video_30_sec_watched_actions",
        "video_60s_watched_actions", "video_thruplay_watched_actions",
        "video_continuous_2_sec_watched_actions",
        "video_play_retention_0_to_15s_actions",
        "video_play_retention_20_to_60s_actions",
        "video_play_retention_graph_actions",
        "cost_per_15_sec_video_view", "cost_per_2_sec_continuous_video_view",
        "cost_per_thruplay", "cost_per_video_view",
        "video_15_sec_watched_actions", "video_30_sec_watched_actions",
        
        # === ENGAGEMENT ===
        "engagement_rate_ranking", "quality_ranking", "conversion_rate_ranking",
        "quality_score_organic", "quality_score_ectr", "quality_score_ecvr",
        "post_engagement", "page_engagement", "messaging_conversations_started",
        "post_reactions", "page_likes", "comment_count", "post_comments",
        "post_shares", "photo_views", "video_views", "link_url_asset",
        
        # === AUDIENCE ET CIBLAGE ===
        "age_targeting", "gender_targeting", "geo_targeting",
        "reach_frequency_predictions", "estimated_ad_recallers",
        "estimated_ad_recall_rate", "estimated_ad_recall_rate_lower_bound",
        "estimated_ad_recall_rate_upper_bound",
        "cost_per_estimated_ad_recallers", "instant_experience_clicks_to_open",
        "instant_experience_clicks_to_start", "instant_experience_outbound_clicks",
        
        # === DEVICE ET PLACEMENT ===
        "device_platform", "platform_position", "publisher_platform",
        "impression_device", "canvas_avg_view_percent", "canvas_avg_view_time",
        
        # === ATTRIBUTION ===
        "attribution_setting", "dda_results", "inline_post_engagement",
        "cost_per_inline_post_engagement", "cost_per_unique_inline_link_click",
        
        # === AUTRES ===
        "auction_bid", "auction_competitiveness", "auction_max_competitor_bid",
        "full_view_impressions", "full_view_reach", 
        "social_spend", "wish_bid", "labels", "location",
        "place_page_name", "qualifying_question_qualify_answer_rate",
    ]
    
    # Tester chaque champ individuellement pour voir lesquels fonctionnent
    valid_fields = []
    invalid_fields = []
    
    # Test rapide avec tous les champs
    url = f"https://graph.facebook.com/v23.0/{account_id}/insights"
    
    # D'abord essayer tous ensemble
    print(f"Test de {len(all_fields)} champs...")
    params = {
        "access_token": token,
        "level": "ad",
        "date_preset": "last_7d",
        "fields": ",".join(all_fields),
        "limit": 1
    }
    
    response = requests.get(url, params=params)
    
    if response.status_code == 200:
        data = response.json()
        if data.get("data"):
            # Récupérer les champs qui sont vraiment retournés
            sample_ad = data["data"][0]
            valid_fields = list(sample_ad.keys())
            print(f"✅ {len(valid_fields)} champs valides trouvés!")
        else:
            print("⚠️ Pas de données retournées")
    else:
        # Si erreur, on teste par batch
        print(f"❌ Erreur globale: {response.json().get('error', {}).get('message', 'Unknown')}")
        print("Test par batch de 20 champs...")
        
        for i in range(0, len(all_fields), 20):
            batch = all_fields[i:i+20]
            params["fields"] = ",".join(batch)
            response = requests.get(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("data"):
                    sample = data["data"][0]
                    for field in batch:
                        if field in sample:
                            valid_fields.append(field)
    
    print(f"\n📋 CHAMPS VALIDES DISPONIBLES: {len(valid_fields)}")
    
    # 2. RÉCUPÉRER TOUTES LES DONNÉES AVEC LES CHAMPS VALIDES
    print("\n📥 RÉCUPÉRATION DES DONNÉES COMPLÈTES...")
    
    if valid_fields:
        params = {
            "access_token": token,
            "level": "ad",
            "date_preset": "last_7d",
            "fields": ",".join(valid_fields),
            "limit": 500
        }
        
        all_ads = []
        next_url = url
        page = 1
        
        while next_url and page <= 10:  # Limite de sécurité
            if page > 1:
                response = requests.get(next_url)
            else:
                response = requests.get(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                ads = data.get("data", [])
                all_ads.extend(ads)
                
                print(f"  Page {page}: {len(ads)} annonces")
                
                # Pagination
                if "paging" in data and "next" in data["paging"]:
                    next_url = data["paging"]["next"]
                    page += 1
                else:
                    break
            else:
                print(f"  ❌ Erreur page {page}")
                break
        
        print(f"\n✅ TOTAL: {len(all_ads)} annonces récupérées")
        
        # 3. ANALYSER LES DONNÉES
        if all_ads:
            print("\n📊 ANALYSE DES DONNÉES DISPONIBLES:")
            print("-" * 40)
            
            # Prendre un échantillon
            sample_ad = all_ads[0]
            
            # Grouper les champs par catégorie
            categories = {
                "Identifiants": ["ad_id", "ad_name", "campaign_id", "campaign_name", "adset_id", "adset_name"],
                "Métriques de base": ["spend", "impressions", "reach", "frequency"],
                "Clics": [f for f in valid_fields if "click" in f],
                "Conversions": ["actions", "conversions", "purchase_roas", "website_purchase_roas"],
                "Vidéo": [f for f in valid_fields if "video" in f],
                "Coûts": [f for f in valid_fields if "cost_per" in f or f in ["cpm", "cpc", "cpp"]],
                "Engagement": [f for f in valid_fields if any(x in f for x in ["engagement", "reactions", "comments", "shares"])],
                "Quality": [f for f in valid_fields if "quality" in f or "ranking" in f],
            }
            
            for category, fields in categories.items():
                available = [f for f in fields if f in sample]
                if available:
                    print(f"\n{category}: {len(available)} champs")
                    for field in available[:5]:  # Montrer les 5 premiers
                        value = sample.get(field)
                        if value:
                            if isinstance(value, (int, float)):
                                print(f"  - {field}: {value:.2f}" if isinstance(value, float) else f"  - {field}: {value}")
                            elif isinstance(value, list) and len(value) > 0:
                                print(f"  - {field}: {len(value)} éléments")
                            else:
                                print(f"  - {field}: {str(value)[:50]}...")
            
            # 4. SAUVEGARDER TOUTES LES DONNÉES
            print("\n💾 SAUVEGARDE DES DONNÉES...")
            
            # JSON complet
            with open("complete_ads_data.json", "w", encoding="utf-8") as f:
                json.dump(all_ads, f, indent=2, ensure_ascii=False)
            print("✅ Données complètes sauvegardées dans complete_ads_data.json")
            
            # Liste des champs disponibles
            with open("available_fields.json", "w") as f:
                json.dump({
                    "valid_fields": sorted(valid_fields),
                    "sample_ad": sample_ad,
                    "total_ads": len(all_ads),
                    "date": datetime.now().isoformat()
                }, f, indent=2)
            print("✅ Liste des champs sauvegardée dans available_fields.json")
            
            # 5. TESTER LES BREAKDOWNS (VENTILATIONS)
            print("\n🔍 TEST DES VENTILATIONS (BREAKDOWNS)...")
            
            breakdowns_to_test = [
                "age", "gender", "country", "region",
                "impression_device", "platform_position",
                "publisher_platform", "device_platform",
                "hourly_stats_aggregated_by_advertiser_time_zone",
                "place_page_id"
            ]
            
            for breakdown in breakdowns_to_test:
                params_breakdown = {
                    "access_token": token,
                    "level": "ad",
                    "date_preset": "last_7d",
                    "fields": "impressions,spend",
                    "breakdowns": breakdown,
                    "limit": 2
                }
                
                response = requests.get(url, params=params_breakdown)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("data"):
                        print(f"  ✅ {breakdown}: Disponible ({len(data['data'])} lignes)")
                else:
                    print(f"  ❌ {breakdown}: Non disponible")
            
            # 6. RÉCUPÉRER LES DÉTAILS DES CRÉATIFS
            print("\n🎨 TEST DES CRÉATIFS DÉTAILLÉS...")
            
            # Prendre quelques ad_ids
            sample_ad_ids = [ad["ad_id"] for ad in all_ads[:3]]
            
            for ad_id in sample_ad_ids:
                ad_url = f"https://graph.facebook.com/v23.0/{ad_id}"
                creative_params = {
                    "access_token": token,
                    "fields": "id,name,status,creative{id,name,title,body,image_url,video_id,thumbnail_url,object_story_spec,link_url,call_to_action_type}"
                }
                
                response = requests.get(ad_url, params=creative_params)
                if response.status_code == 200:
                    ad_detail = response.json()
                    if "creative" in ad_detail:
                        print(f"\n  Annonce {ad_id}:")
                        creative = ad_detail["creative"]
                        print(f"    - Titre: {creative.get('title', 'N/A')}")
                        print(f"    - Corps: {creative.get('body', 'N/A')[:50]}...")
                        print(f"    - CTA: {creative.get('call_to_action_type', 'N/A')}")
                        if creative.get("video_id"):
                            print(f"    - Type: VIDÉO (ID: {creative['video_id']})")
                        elif creative.get("image_url"):
                            print(f"    - Type: IMAGE")
            
            print("\n" + "=" * 80)
            print("✅ AUDIT COMPLET TERMINÉ!")
            print(f"📊 Résumé:")
            print(f"  - {len(all_ads)} annonces analysées")
            print(f"  - {len(valid_fields)} champs de données disponibles")
            print(f"  - Fichiers créés: complete_ads_data.json, available_fields.json")

if __name__ == "__main__":
    get_all_possible_fields()