#!/usr/bin/env python3
"""
Script pour récupérer les URLs des créatifs (images et vidéos) des annonces Meta.
"""

import requests
import json
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

# Configuration
FB_TOKEN = os.getenv('FB_TOKEN')
if not FB_TOKEN:
    print("❌ Erreur: FB_TOKEN non trouvé dans le .env")
    exit(1)

def get_ads_with_creatives():
    """Récupère les annonces avec leurs créatifs."""
    
    # D'abord, obtenir les comptes
    accounts_url = "https://graph.facebook.com/v23.0/me/adaccounts"
    accounts_params = {
        "access_token": FB_TOKEN,
        "fields": "name,account_id",
        "limit": 100
    }
    
    response = requests.get(accounts_url, params=accounts_params)
    accounts = response.json().get("data", [])
    
    print(f"📊 {len(accounts)} comptes trouvés")
    
    # Récupérer les annonces des 7 derniers jours
    since_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    
    ads_with_creatives = []
    
    for account in accounts[:5]:  # Limiter aux 5 premiers comptes pour le test
        account_id = account['account_id']
        account_name = account['name']
        
        print(f"\n🔍 Analyse du compte: {account_name}")
        
        # Récupérer les insights des annonces
        insights_url = f"https://graph.facebook.com/v23.0/{account_id}/insights"
        insights_params = {
            "access_token": FB_TOKEN,
            "level": "ad",
            "fields": "ad_id,ad_name,spend,purchase_roas",
            "filtering": f"[{{'field':'spend','operator':'GREATER_THAN','value':100}}]",  # Seuil plus bas pour tester
            "time_range": f"{{'since':'{since_date}','until':'today'}}",
            "limit": 10
        }
        
        response = requests.get(insights_url, params=insights_params)
        insights = response.json().get("data", [])
        
        # Pour chaque annonce, récupérer les détails du créatif
        for insight in insights:
            ad_id = insight.get('ad_id')
            ad_name = insight.get('ad_name')
            spend = float(insight.get('spend', 0))
            
            # Récupérer les détails du créatif
            ad_url = f"https://graph.facebook.com/v23.0/{ad_id}"
            creative_params = {
                "access_token": FB_TOKEN,
                "fields": "creative{id,name,title,body,image_url,video_id,thumbnail_url,object_story_spec,instagram_permalink_url,effective_instagram_story_id,effective_object_story_id}"
            }
            
            try:
                response = requests.get(ad_url, params=creative_params)
                ad_data = response.json()
                
                if 'creative' in ad_data:
                    creative = ad_data['creative']
                    
                    # Déterminer le type et l'URL
                    media_url = None
                    media_type = None
                    
                    if creative.get('video_id'):
                        # Pour les vidéos, on peut construire plusieurs URLs possibles
                        video_id = creative['video_id']
                        media_type = "VIDEO"
                        # URL de la vidéo sur Facebook
                        media_url = f"https://www.facebook.com/{video_id}"
                        # Alternative: thumbnail pour preview
                        thumbnail = creative.get('thumbnail_url', '')
                    elif creative.get('image_url'):
                        media_type = "IMAGE"
                        media_url = creative['image_url']
                    elif creative.get('instagram_permalink_url'):
                        media_type = "INSTAGRAM"
                        media_url = creative['instagram_permalink_url']
                    
                    if media_url:
                        ads_with_creatives.append({
                            'account': account_name,
                            'ad_name': ad_name,
                            'spend': spend,
                            'media_type': media_type,
                            'media_url': media_url,
                            'thumbnail': creative.get('thumbnail_url', ''),
                            'title': creative.get('title', ''),
                            'body': creative.get('body', '')
                        })
                        
                        print(f"  ✅ {ad_name}")
                        print(f"     Type: {media_type}")
                        print(f"     URL: {media_url[:100]}...")
                        
            except Exception as e:
                print(f"  ❌ Erreur pour {ad_name}: {e}")
    
    return ads_with_creatives

def main():
    print("🚀 Récupération des URLs des créatifs...")
    print("=" * 80)
    
    ads = get_ads_with_creatives()
    
    # Sauvegarder les résultats
    output_file = f"creative_urls_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(ads, f, ensure_ascii=False, indent=2)
    
    print("\n" + "=" * 80)
    print(f"✅ {len(ads)} annonces avec créatifs trouvées")
    print(f"📁 Résultats sauvegardés dans: {output_file}")
    
    # Afficher un résumé
    print("\n📊 Résumé par type de média:")
    media_counts = {}
    for ad in ads:
        media_type = ad['media_type']
        media_counts[media_type] = media_counts.get(media_type, 0) + 1
    
    for media_type, count in media_counts.items():
        print(f"  - {media_type}: {count}")

if __name__ == "__main__":
    main()