#!/usr/bin/env python3
"""
Récupère les top annonces avec leurs URLs de créatifs.
"""

import requests
import json
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

FB_TOKEN = os.getenv('FB_TOKEN')

def get_top_ads_with_creatives():
    """Récupère les top annonces avec leurs créatifs."""
    
    # D'abord, obtenir les comptes principaux
    accounts_url = "https://graph.facebook.com/v23.0/me/adaccounts"
    accounts_params = {
        "access_token": FB_TOKEN,
        "fields": "name,account_id",
        "limit": 100
    }
    
    response = requests.get(accounts_url, params=accounts_params)
    accounts = response.json().get("data", [])
    
    print(f"📊 Analyse de {len(accounts)} comptes...")
    
    # Collecter toutes les annonces
    all_ads = []
    since_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    
    for account in accounts:
        account_id = account['account_id']
        
        # Récupérer les ads avec insights
        ads_url = f"https://graph.facebook.com/v23.0/{account_id}/ads"
        ads_params = {
            "access_token": FB_TOKEN,
            "fields": "id,name,insights{spend,purchase_roas,impressions,ctr}",
            "time_range": f"{{'since':'{since_date}','until':'today'}}",
            "limit": 50,
            "effective_status": "['ACTIVE']"
        }
        
        try:
            response = requests.get(ads_url, params=ads_params)
            ads_data = response.json().get("data", [])
            
            for ad in ads_data:
                if 'insights' in ad and ad['insights'].get('data'):
                    insight = ad['insights']['data'][0]
                    spend = float(insight.get('spend', 0))
                    
                    # Filtrer par spend > 3000 MXN
                    if spend > 3000:
                        roas_data = insight.get('purchase_roas', [])
                        roas = float(roas_data[0]['value']) if roas_data else 0
                        
                        all_ads.append({
                            'ad_id': ad['id'],
                            'name': ad['name'],
                            'spend': spend,
                            'roas': roas,
                            'ctr': float(insight.get('ctr', 0)),
                            'account': account['name']
                        })
        except:
            continue
    
    # Trier par ROAS
    all_ads.sort(key=lambda x: x['roas'], reverse=True)
    
    # Prendre le top 10
    top_ads = all_ads[:10]
    
    print(f"\n🎯 Top {len(top_ads)} annonces trouvées")
    print("=" * 80)
    
    # Récupérer les créatifs pour chaque top ad
    for i, ad in enumerate(top_ads, 1):
        ad_id = ad['ad_id']
        
        # Récupérer les détails du créatif
        creative_url = f"https://graph.facebook.com/v23.0/{ad_id}"
        creative_params = {
            "access_token": FB_TOKEN,
            "fields": "creative{id,name,image_url,video_id,thumbnail_url,instagram_permalink_url,object_story_spec}"
        }
        
        try:
            response = requests.get(creative_url, params=creative_params)
            data = response.json()
            
            if 'creative' in data:
                creative = data['creative']
                
                # Déterminer le type et l'URL
                if creative.get('instagram_permalink_url'):
                    ad['media_url'] = creative['instagram_permalink_url']
                    ad['media_type'] = 'INSTAGRAM'
                elif creative.get('video_id'):
                    video_id = creative['video_id']
                    ad['media_url'] = f"https://www.facebook.com/watch/?v={video_id}"
                    ad['media_type'] = 'VIDEO'
                elif creative.get('image_url'):
                    ad['media_url'] = creative['image_url']
                    ad['media_type'] = 'IMAGE'
                else:
                    ad['media_url'] = None
                    ad['media_type'] = 'UNKNOWN'
                
                ad['thumbnail'] = creative.get('thumbnail_url', '')
                
                print(f"\n{i}. {ad['name'][:50]}...")
                print(f"   ROAS: {ad['roas']:.2f}x")
                print(f"   Spend: ${ad['spend']:.0f} MXN")
                print(f"   Type: {ad['media_type']}")
                if ad['media_url']:
                    print(f"   URL: {ad['media_url'][:80]}...")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
            ad['media_url'] = None
            ad['media_type'] = 'ERROR'
    
    return top_ads

# Exécuter
if __name__ == "__main__":
    print("🚀 Récupération des top annonces avec URLs...")
    print("=" * 80)
    
    ads = get_top_ads_with_creatives()
    
    # Sauvegarder
    output = {
        'timestamp': datetime.now().isoformat(),
        'ads': ads
    }
    
    with open('top_ads_urls.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print("\n" + "=" * 80)
    print(f"✅ {len(ads)} annonces sauvegardées dans top_ads_urls.json")