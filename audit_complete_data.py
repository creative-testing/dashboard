#!/usr/bin/env python3
"""
Script d'audit pour vérifier qu'on récupère TOUTES les données possibles
"""
import json
import requests
from datetime import datetime, timedelta
from meta_insights import MetaInsightsFetcher
from config import MetaConfig

def audit_all_data():
    print("🔍 AUDIT COMPLET DES DONNÉES META ADS")
    print("=" * 80)
    
    fetcher = MetaInsightsFetcher()
    
    # 1. TEST DIFFÉRENTES PÉRIODES
    print("\n📅 TEST DE DIFFÉRENTES PÉRIODES:")
    print("-" * 40)
    periods = [
        ("today", "today"),
        ("yesterday", "yesterday"),
        ("last_7d", "7 derniers jours"),
        ("last_30d", "30 derniers jours"),
        ("last_90d", "90 derniers jours"),
    ]
    
    for period, desc in periods:
        try:
            url = f"{MetaConfig.BASE_URL}/{fetcher.account_id}/insights"
            params = {
                "access_token": fetcher.access_token,
                "level": "ad",
                "date_preset": period,
                "fields": "ad_id",
                "limit": 1,
                "summary": "true"
            }
            response = requests.get(url, params=params)
            data = response.json()
            
            total = len(data.get("data", []))
            summary = data.get("summary", {})
            paging = data.get("paging", {})
            
            print(f"\n{desc} ({period}):")
            print(f"  Résultats: {total}")
            if "summary" in data:
                print(f"  Summary: {summary}")
            if "summary" in paging:
                print(f"  Total dans paging: {paging.get('summary', {})}")
                
        except Exception as e:
            print(f"  ❌ Erreur: {e}")
    
    # 2. RÉCUPÉRER TOUS LES CHAMPS POSSIBLES
    print("\n\n📊 TEST DE TOUS LES CHAMPS DISPONIBLES:")
    print("-" * 40)
    
    # Liste exhaustive des champs possibles
    all_possible_fields = [
        # Identifiants
        "ad_id", "ad_name", "campaign_id", "campaign_name", 
        "adset_id", "adset_name", "account_id", "account_name",
        
        # Statuts
        "status", "effective_status", "configured_status",
        
        # Dates
        "created_time", "updated_time", "start_time", "stop_time",
        
        # Budget
        "budget_remaining", "daily_budget", "lifetime_budget",
        
        # Métriques de base
        "impressions", "reach", "frequency", "spend",
        
        # Clics
        "clicks", "unique_clicks", "all_clicks", "button_clicks",
        "link_clicks", "unique_link_clicks", "outbound_clicks",
        "unique_outbound_clicks", "social_clicks", "unique_social_clicks",
        
        # Taux
        "ctr", "unique_ctr", "cpm", "cpp", "cpc", "cost_per_unique_click",
        
        # Conversions et actions
        "actions", "action_values", "conversions", "conversion_values",
        "cost_per_action_type", "cost_per_conversion",
        "purchase_roas", "website_purchase_roas", "mobile_app_purchase_roas",
        
        # Attribution
        "attribution_setting", "inline_link_clicks", "inline_post_engagement",
        
        # Vidéo (tous les points de vue)
        "video_play_actions", "video_play_curve_actions",
        "video_avg_time_watched_actions", "video_p25_watched_actions",
        "video_p50_watched_actions", "video_p75_watched_actions",
        "video_p95_watched_actions", "video_p100_watched_actions",
        "video_thruplay_watched_actions", "video_15s_watched_actions",
        "video_30_sec_watched_actions", "video_60_sec_watched_actions",
        "video_continuous_2_sec_watched_actions",
        "video_play_retention_0_to_15s_actions",
        "video_play_retention_20_to_60s_actions",
        "video_play_retention_graph_actions",
        
        # Engagement
        "engagement_rate_ranking", "quality_ranking", "conversion_rate_ranking",
        "post_engagement", "page_engagement", "post_reactions",
        "comments", "shares", "photo_views", "video_views",
        
        # Audience
        "age_targeting", "gender_targeting", "geo_targeting",
        "place_page_name", "location",
        
        # Device
        "device_platform", "platform_position", "publisher_platform",
        "impression_device", 
        
        # Catalogue
        "catalog_segment_actions", "catalog_segment_value",
        "website_ctr", "website_conversions",
        
        # DDA (Data-Driven Attribution)
        "dda_results", "instant_experience_clicks_to_open",
        "instant_experience_clicks_to_start", "instant_experience_outbound_clicks",
        
        # Quality & Delivery
        "quality_score_organic", "quality_score_ectr", "quality_score_ecvr",
        "auction_bid", "auction_competitiveness", "auction_max_competitor_bid",
        
        # Canvas
        "canvas_avg_view_percent", "canvas_avg_view_time",
        
        # Coûts détaillés
        "cost_per_15_sec_video_view", "cost_per_2_sec_continuous_video_view",
        "cost_per_ad_click", "cost_per_dda_countby_convs",
        "cost_per_estimated_ad_recallers", "cost_per_inline_link_click",
        "cost_per_inline_post_engagement", "cost_per_one_thousand_ad_impression",
        "cost_per_outbound_click", "cost_per_thruplay",
        "cost_per_unique_action_type", "cost_per_unique_inline_link_click",
        "cost_per_unique_outbound_click",
        
        # Autres
        "estimated_ad_recall_rate", "estimated_ad_recall_rate_lower_bound",
        "estimated_ad_recall_rate_upper_bound", "estimated_ad_recallers",
        "full_view_impressions", "full_view_reach",
        "inline_link_click_ctr", "objective",
        "optimization_goal", "qualifying_question_qualify_answer_rate",
        "social_spend", "wish_bid",
    ]
    
    # Tester par batch
    print("\nTest avec TOUS les champs possibles...")
    batch_size = 50
    valid_fields = []
    invalid_fields = []
    
    for i in range(0, len(all_possible_fields), batch_size):
        batch = all_possible_fields[i:i+batch_size]
        fields_str = ",".join(batch)
        
        try:
            url = f"{MetaConfig.BASE_URL}/{fetcher.account_id}/insights"
            params = {
                "access_token": fetcher.access_token,
                "level": "ad",
                "date_preset": "yesterday",
                "fields": fields_str,
                "limit": 1
            }
            response = requests.get(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("data"):
                    # Vérifier quels champs sont vraiment retournés
                    returned_fields = set(data["data"][0].keys())
                    for field in batch:
                        if field in returned_fields or field in str(data):
                            valid_fields.append(field)
                        else:
                            invalid_fields.append(field)
            else:
                # Si erreur, tester champ par champ
                for field in batch:
                    try:
                        params["fields"] = field
                        response = requests.get(url, params=params)
                        if response.status_code == 200:
                            valid_fields.append(field)
                        else:
                            invalid_fields.append(field)
                    except:
                        invalid_fields.append(field)
                        
        except Exception as e:
            invalid_fields.extend(batch)
    
    print(f"\n✅ Champs valides trouvés: {len(valid_fields)}")
    print(f"❌ Champs invalides/non disponibles: {len(invalid_fields)}")
    
    # 3. RÉCUPÉRER LES BREAKDOWNS (ventilations)
    print("\n\n🔍 TEST DES BREAKDOWNS (VENTILATIONS):")
    print("-" * 40)
    
    breakdowns = [
        "age", "gender", "country", "region", "dma",
        "impression_device", "platform_position", 
        "publisher_platform", "device_platform",
        "product_id", "frequency_value",
        "hourly_stats_aggregated_by_advertiser_time_zone",
        "hourly_stats_aggregated_by_audience_time_zone",
        "place_page_id", "skan_conversion_id",
    ]
    
    for breakdown in breakdowns:
        try:
            url = f"{MetaConfig.BASE_URL}/{fetcher.account_id}/insights"
            params = {
                "access_token": fetcher.access_token,
                "level": "ad",
                "date_preset": "yesterday",
                "fields": "impressions,spend",
                "breakdowns": breakdown,
                "limit": 2
            }
            response = requests.get(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                print(f"  ✅ {breakdown}: {len(data.get('data', []))} résultats")
            else:
                print(f"  ❌ {breakdown}: Non disponible")
                
        except Exception as e:
            print(f"  ❌ {breakdown}: Erreur")
    
    # 4. RÉCUPÉRER LES CRÉATIFS DÉTAILLÉS
    print("\n\n🎨 TEST DES DÉTAILS CRÉATIFS:")
    print("-" * 40)
    
    # D'abord récupérer quelques ad_ids
    url = f"{MetaConfig.BASE_URL}/{fetcher.account_id}/insights"
    params = {
        "access_token": fetcher.access_token,
        "level": "ad",
        "date_preset": "last_7d",
        "fields": "ad_id",
        "limit": 5
    }
    response = requests.get(url, params=params)
    ad_ids = [item["ad_id"] for item in response.json().get("data", [])]
    
    if ad_ids:
        # Tester l'expansion des créatifs
        ad_id = ad_ids[0]
        creative_fields = [
            "id", "name", "title", "body", "caption", "description",
            "link_url", "link_caption", "link_description", 
            "call_to_action_type", "object_type", "status",
            "thumbnail_url", "image_url", "image_hash", "video_id",
            "object_story_spec", "object_story_id", "object_url",
            "template_url", "template_app_link_spec",
            "instagram_permalink_url", "instagram_story_id",
            "effective_instagram_story_id", "effective_object_story_id",
            "degrees_of_freedom_spec", "recommender_settings",
            "asset_feed_spec", "link_og_id", "object_id",
            "place_page_set_id", "product_set_id",
        ]
        
        url = f"{MetaConfig.BASE_URL}/{ad_id}"
        params = {
            "access_token": fetcher.access_token,
            "fields": f"id,name,creative{{{','.join(creative_fields[:10])}}}",
        }
        
        try:
            response = requests.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                if "creative" in data:
                    print(f"✅ Créatif récupéré pour l'annonce {ad_id}")
                    print(f"   Champs disponibles: {list(data['creative'].keys())}")
        except Exception as e:
            print(f"❌ Erreur créatif: {e}")
    
    # 5. AFFICHER LES CHAMPS QU'ON N'UTILISE PAS ENCORE
    print("\n\n💡 CHAMPS DISPONIBLES NON UTILISÉS:")
    print("-" * 40)
    
    current_fields = set(MetaConfig.INSIGHTS_FIELDS)
    available_not_used = set(valid_fields) - current_fields
    
    if available_not_used:
        print("Champs valides mais non récupérés actuellement:")
        for field in sorted(available_not_used):
            print(f"  - {field}")
    else:
        print("✅ Tous les champs disponibles sont déjà utilisés!")
    
    # 6. SAUVEGARDER LE RAPPORT
    report = {
        "audit_date": datetime.now().isoformat(),
        "valid_fields": sorted(valid_fields),
        "invalid_fields": sorted(invalid_fields),
        "current_fields": sorted(list(current_fields)),
        "missing_fields": sorted(list(available_not_used))
    }
    
    with open("audit_report.json", "w") as f:
        json.dump(report, f, indent=2)
    
    print("\n\n📁 Rapport complet sauvegardé dans audit_report.json")
    print(f"\n📊 RÉSUMÉ FINAL:")
    print(f"  - Champs valides disponibles: {len(valid_fields)}")
    print(f"  - Champs actuellement utilisés: {len(current_fields)}")
    print(f"  - Champs manquants: {len(available_not_used)}")

if __name__ == "__main__":
    audit_all_data()