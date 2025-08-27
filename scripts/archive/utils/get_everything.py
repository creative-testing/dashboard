#!/usr/bin/env python3
"""
Récupérer ABSOLUMENT TOUT ce qui est disponible
"""
import json
import requests
from meta_insights import MetaInsightsFetcher
from dotenv import load_dotenv
import os

load_dotenv()

def get_absolutely_everything():
    print("🚀 RÉCUPÉRATION DE TOUTES LES DONNÉES DISPONIBLES")
    print("=" * 80)
    
    token = os.getenv("FACEBOOK_ACCESS_TOKEN")
    if not token:
        raise SystemExit("FACEBOOK_ACCESS_TOKEN not set. Define it in .env")
    account_id = "act_297112083495970"
    
    # 1. RÉCUPÉRER LES INSIGHTS AVEC TOUS LES CHAMPS
    print("\n📊 1. INSIGHTS COMPLETS...")
    fetcher = MetaInsightsFetcher()
    insights = fetcher.fetch_insights(filtering="no_filter", limit=200)
    processed = fetcher.process_insights(insights)
    
    print(f"✅ {len(insights)} annonces avec insights")
    if insights:
        print(f"📋 {len(insights[0].keys())} champs par annonce")
    
    # 2. RÉCUPÉRER LES DÉTAILS CRÉATIFS
    print("\n🎨 2. DÉTAILS CRÉATIFS...")
    creative_details = []
    
    if insights:
        # Prendre un échantillon d'annonces
        sample_ads = insights[:10]
        
        for ad in sample_ads:
            ad_id = ad["ad_id"]
            url = f"https://graph.facebook.com/v23.0/{ad_id}"
            params = {
                "access_token": token,
                "fields": "id,name,status,effective_status,creative{id,name,title,body,image_url,image_hash,video_id,thumbnail_url,object_story_spec,link_url,call_to_action_type,instagram_permalink_url}"
            }
            
            try:
                response = requests.get(url, params=params)
                if response.status_code == 200:
                    ad_detail = response.json()
                    creative_details.append(ad_detail)
                    
                    if "creative" in ad_detail:
                        creative = ad_detail["creative"]
                        print(f"\n  Annonce: {ad['ad_name']}")
                        if creative.get("title"):
                            print(f"    Titre: {creative['title']}")
                        if creative.get("body"):
                            print(f"    Texte: {creative['body'][:100]}...")
                        if creative.get("call_to_action_type"):
                            print(f"    CTA: {creative['call_to_action_type']}")
                        if creative.get("video_id"):
                            print(f"    Format: VIDÉO (ID: {creative['video_id']})")
                        elif creative.get("image_url"):
                            print(f"    Format: IMAGE")
                            print(f"    URL: {creative['image_url'][:50]}...")
            except Exception as e:
                print(f"  ❌ Erreur pour {ad_id}: {e}")
    
    # 3. RÉCUPÉRER LES BREAKDOWNS
    print("\n📈 3. VENTILATIONS (BREAKDOWNS)...")
    
    breakdowns_data = {}
    breakdowns = ["age", "gender", "country", "impression_device", "publisher_platform"]
    
    for breakdown in breakdowns:
        try:
            url = f"https://graph.facebook.com/v23.0/{account_id}/insights"
            params = {
                "access_token": token,
                "level": "ad",
                "date_preset": "last_7d",
                "fields": "ad_id,ad_name,impressions,spend,clicks,actions",
                "breakdowns": breakdown,
                "limit": 100
            }
            
            response = requests.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                results = data.get("data", [])
                breakdowns_data[breakdown] = results
                
                print(f"\n  {breakdown.upper()}: {len(results)} lignes")
                
                # Montrer un échantillon
                if results:
                    sample_breakdown = {}
                    for item in results[:5]:
                        key = item.get(breakdown, "unknown")
                        if key not in sample_breakdown:
                            sample_breakdown[key] = {
                                "impressions": 0,
                                "spend": 0,
                                "clicks": 0
                            }
                        sample_breakdown[key]["impressions"] += int(item.get("impressions", 0))
                        sample_breakdown[key]["spend"] += float(item.get("spend", 0))
                        sample_breakdown[key]["clicks"] += int(item.get("clicks", 0))
                    
                    for key, metrics in sample_breakdown.items():
                        print(f"    • {key}: {metrics['impressions']:,} impr, ${metrics['spend']:.2f}")
                        
        except Exception as e:
            print(f"  ❌ {breakdown}: Erreur - {e}")
    
    # 4. RÉCUPÉRER LES INFORMATIONS AU NIVEAU CAMPAGNE
    print("\n📁 4. DONNÉES AU NIVEAU CAMPAGNE...")
    
    try:
        url = f"https://graph.facebook.com/v23.0/{account_id}/campaigns"
        params = {
            "access_token": token,
            "fields": "id,name,status,objective,daily_budget,lifetime_budget,spend_cap,created_time,start_time,stop_time",
            "limit": 50
        }
        
        response = requests.get(url, params=params)
        if response.status_code == 200:
            campaigns = response.json().get("data", [])
            print(f"✅ {len(campaigns)} campagnes trouvées")
            
            for campaign in campaigns[:5]:
                print(f"  • {campaign.get('name')}: {campaign.get('objective')} - Status: {campaign.get('status')}")
    except:
        pass
    
    # 5. SAUVEGARDER TOUT
    print("\n💾 5. SAUVEGARDE DES DONNÉES COMPLÈTES...")
    
    complete_data = {
        "metadata": {
            "date": os.popen("date").read().strip(),
            "account_id": account_id,
            "total_ads": len(insights)
        },
        "insights": insights,
        "processed_insights": processed,
        "creative_samples": creative_details,
        "breakdowns": breakdowns_data
    }
    
    with open("everything_data.json", "w", encoding="utf-8") as f:
        json.dump(complete_data, f, indent=2, ensure_ascii=False)
    
    print("✅ Toutes les données sauvegardées dans everything_data.json")
    
    # 6. RÉSUMÉ
    print("\n" + "=" * 80)
    print("📊 RÉSUMÉ - CE QU'ON A RÉCUPÉRÉ:")
    print("-" * 40)
    
    total_fields = len(insights[0].keys()) if insights else 0
    print(f"✅ Insights: {len(insights)} annonces × {total_fields} champs")
    print(f"✅ Créatifs détaillés: {len(creative_details)} exemples")
    print(f"✅ Breakdowns: {len(breakdowns_data)} types de ventilation")
    
    if breakdowns_data:
        for breakdown, data in breakdowns_data.items():
            if data:
                unique_values = set()
                for item in data:
                    unique_values.add(item.get(breakdown, "unknown"))
                print(f"  • {breakdown}: {len(unique_values)} valeurs uniques")
    
    print("\n🎯 CONCLUSION: On récupère maintenant TOUT ce qui est disponible via l'API!")

if __name__ == "__main__":
    get_absolutely_everything()
