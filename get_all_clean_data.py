#!/usr/bin/env python3
"""
Script optimisé pour récupérer TOUTES les données possibles des 7 derniers jours
"""
import requests
import json
from datetime import datetime
from dotenv import load_dotenv
import os

load_dotenv()

def get_all_data():
    token = os.getenv("FB_TOKEN")
    account_id = "act_297112083495970"
    
    print("🔍 RÉCUPÉRATION COMPLÈTE DES DONNÉES (7 DERNIERS JOURS)")
    print("=" * 80)
    
    # Liste des champs testés et validés
    insights_fields = [
        # Identifiants
        "ad_id", "ad_name", "campaign_id", "campaign_name",
        "adset_id", "adset_name", "account_id", "account_name",
        
        # Dates
        "date_start", "date_stop",
        
        # Métriques principales
        "impressions", "reach", "frequency", "spend",
        "objective", "optimization_goal",
        
        # Clics (tous types)
        "clicks", "unique_clicks", 
        "link_clicks", "unique_link_clicks",
        "outbound_clicks", "unique_outbound_clicks",
        "inline_link_clicks", "unique_inline_link_clicks",
        
        # Taux et coûts
        "ctr", "unique_ctr", "inline_link_click_ctr",
        "cpm", "cpp", "cpc",
        "cost_per_inline_link_click",
        "cost_per_outbound_click",
        
        # Actions et conversions
        "actions", "action_values",
        "conversions", "conversion_values",
        "cost_per_action_type",
        "cost_per_conversion",
        "website_conversions",
        "catalog_segment_actions",
        "catalog_segment_value",
        
        # ROAS
        "purchase_roas",
        "website_purchase_roas",
        
        # Vidéo
        "video_play_actions",
        "video_avg_time_watched_actions",
        "video_p25_watched_actions",
        "video_p50_watched_actions", 
        "video_p75_watched_actions",
        "video_p95_watched_actions",
        "video_p100_watched_actions",
        "video_thruplay_watched_actions",
        "video_continuous_2_sec_watched_actions",
        "cost_per_thruplay",
        
        # Engagement et qualité
        "engagement_rate_ranking",
        "quality_ranking",
        "conversion_rate_ranking",
        "post_engagement",
        "page_engagement",
        
        # Attribution
        "attribution_setting",
        "inline_post_engagement",
        
        # Device
        "device_platform",
        "publisher_platform",
        
        # Autres
        "social_spend",
        "location",
    ]
    
    # 1. RÉCUPÉRER LES INSIGHTS
    print("\n📊 RÉCUPÉRATION DES INSIGHTS...")
    
    url = f"https://graph.facebook.com/v23.0/{account_id}/insights"
    params = {
        "access_token": token,
        "level": "ad",
        "date_preset": "last_7d",
        "fields": ",".join(insights_fields),
        "limit": 500
    }
    
    all_ads = []
    page = 1
    
    try:
        response = requests.get(url, params=params)
        
        while response.status_code == 200:
            data = response.json()
            ads = data.get("data", [])
            
            if not ads:
                break
                
            all_ads.extend(ads)
            print(f"  Page {page}: {len(ads)} annonces récupérées")
            
            # Pagination
            if "paging" in data and "next" in data["paging"]:
                response = requests.get(data["paging"]["next"])
                page += 1
            else:
                break
                
            if page > 10:  # Sécurité
                break
                
    except Exception as e:
        print(f"❌ Erreur: {e}")
    
    print(f"\n✅ TOTAL INSIGHTS: {len(all_ads)} annonces")
    
    # 2. ANALYSER LES CHAMPS DISPONIBLES
    if all_ads:
        sample = all_ads[0]
        print(f"\n📋 CHAMPS DISPONIBLES: {len(sample.keys())} champs")
        
        # Analyser les types de données
        print("\n📊 ANALYSE DES DONNÉES:")
        print("-" * 40)
        
        # Métriques clés
        total_spend = sum(float(ad.get("spend", 0)) for ad in all_ads)
        total_impressions = sum(int(ad.get("impressions", 0)) for ad in all_ads)
        total_clicks = sum(int(ad.get("clicks", 0)) for ad in all_ads)
        
        print(f"💰 Dépense totale: ${total_spend:,.2f}")
        print(f"👁️ Impressions totales: {total_impressions:,}")
        print(f"👆 Clics totaux: {total_clicks:,}")
        
        # Analyser les actions
        all_actions = []
        for ad in all_ads:
            if "actions" in ad and ad["actions"]:
                for action in ad["actions"]:
                    all_actions.append(action["action_type"])
        
        unique_actions = set(all_actions)
        if unique_actions:
            print(f"\n📌 Types d'actions disponibles: {len(unique_actions)}")
            for action_type in sorted(unique_actions)[:10]:
                count = all_actions.count(action_type)
                print(f"  - {action_type}: {count} occurrences")
        
        # Analyser les vidéos
        video_ads = [ad for ad in all_ads if ad.get("video_play_actions")]
        print(f"\n🎥 Annonces vidéo: {len(video_ads)}/{len(all_ads)}")
        
        # 3. RÉCUPÉRER LES DÉTAILS DES CRÉATIFS
        print("\n🎨 RÉCUPÉRATION DES CRÉATIFS...")
        
        # Prendre un échantillon d'ad_ids
        sample_ids = [ad["ad_id"] for ad in all_ads[:5]]
        creative_details = []
        
        for ad_id in sample_ids:
            ad_url = f"https://graph.facebook.com/v23.0/{ad_id}"
            creative_params = {
                "access_token": token,
                "fields": "id,name,status,effective_status,creative{id,name,title,body,image_url,image_hash,video_id,thumbnail_url,object_story_spec,object_story_id,link_url,call_to_action_type,template_url}"
            }
            
            try:
                response = requests.get(ad_url, params=creative_params)
                if response.status_code == 200:
                    ad_detail = response.json()
                    creative_details.append(ad_detail)
                    
                    if "creative" in ad_detail:
                        creative = ad_detail["creative"]
                        print(f"\n  Annonce: {ad_detail.get('name', 'N/A')}")
                        print(f"    Status: {ad_detail.get('effective_status', 'N/A')}")
                        if creative.get("title"):
                            print(f"    Titre: {creative['title']}")
                        if creative.get("body"):
                            print(f"    Texte: {creative['body'][:100]}...")
                        if creative.get("call_to_action_type"):
                            print(f"    CTA: {creative['call_to_action_type']}")
                        if creative.get("video_id"):
                            print(f"    Format: VIDÉO")
                        elif creative.get("image_url"):
                            print(f"    Format: IMAGE")
            except:
                pass
        
        # 4. TESTER LES BREAKDOWNS
        print("\n📈 TEST DES VENTILATIONS (BREAKDOWNS)...")
        
        breakdown_tests = ["age", "gender", "country", "impression_device", "publisher_platform"]
        available_breakdowns = []
        
        for breakdown in breakdown_tests:
            test_params = {
                "access_token": token,
                "level": "ad",
                "date_preset": "last_7d",
                "fields": "impressions,spend",
                "breakdowns": breakdown,
                "limit": 2
            }
            
            try:
                response = requests.get(url, params=test_params)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("data"):
                        available_breakdowns.append(breakdown)
                        print(f"  ✅ {breakdown}: Disponible")
                        # Montrer un exemple
                        sample_breakdown = data["data"][0]
                        if breakdown in sample_breakdown:
                            print(f"      Exemple: {sample_breakdown[breakdown]}")
            except:
                pass
        
        # 5. SAUVEGARDER TOUTES LES DONNÉES
        print("\n💾 SAUVEGARDE DES DONNÉES...")
        
        # Créer un rapport complet
        report = {
            "metadata": {
                "date": datetime.now().isoformat(),
                "account_id": account_id,
                "period": "last_7d",
                "total_ads": len(all_ads),
                "total_spend": total_spend,
                "total_impressions": total_impressions
            },
            "available_fields": list(sample.keys()) if all_ads else [],
            "available_breakdowns": available_breakdowns,
            "unique_action_types": list(unique_actions) if unique_actions else [],
            "insights_data": all_ads,
            "creative_samples": creative_details
        }
        
        with open("complete_7days_data.json", "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print("✅ Données complètes sauvegardées dans complete_7days_data.json")
        
        # Créer un CSV simplifié
        if all_ads:
            import csv
            
            # Sélectionner les champs principaux pour le CSV
            csv_fields = [
                "ad_id", "ad_name", "campaign_name", "adset_name",
                "spend", "impressions", "reach", "clicks", "ctr", "cpm",
                "link_clicks", "unique_clicks", "conversions"
            ]
            
            with open("ads_7days_summary.csv", "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=csv_fields, extrasaction='ignore')
                writer.writeheader()
                
                for ad in all_ads:
                    # Extraire les conversions si disponibles
                    conversions = 0
                    if "actions" in ad:
                        for action in ad["actions"]:
                            if action["action_type"] in ["purchase", "omni_purchase"]:
                                conversions = int(action["value"])
                                break
                    ad["conversions"] = conversions
                    
                    writer.writerow(ad)
            
            print("✅ Résumé CSV sauvegardé dans ads_7days_summary.csv")
        
        print("\n" + "=" * 80)
        print("📊 RÉSUMÉ FINAL:")
        print(f"  ✅ {len(all_ads)} annonces avec insights complets")
        print(f"  ✅ {len(sample.keys()) if all_ads else 0} champs de données par annonce")
        print(f"  ✅ {len(available_breakdowns)} types de ventilation disponibles")
        print(f"  ✅ {len(creative_details)} exemples de créatifs détaillés")
        print(f"  ✅ {len(unique_actions)} types d'actions/conversions")

if __name__ == "__main__":
    get_all_data()