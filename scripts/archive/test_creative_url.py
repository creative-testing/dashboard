#!/usr/bin/env python3
"""
Test simple pour récupérer une URL de créatif.
"""

import requests
import os
from dotenv import load_dotenv

load_dotenv()

FB_TOKEN = os.getenv('FB_TOKEN')

# Prendre une annonce qu'on sait active (depuis notre CSV)
# Par exemple: RATON PEREZ CATY avec 10262 impressions
test_ads = [
    "6867984162740",  # RATON PEREZ CATY
    "6820250028540",  # BOTANICAL BLUE BOX IG
    "6761146071028",  # Video 2 - Preparando etiquetas
]

for ad_id in test_ads:
    print(f"\n🔍 Test pour l'annonce {ad_id}:")
    print("-" * 40)
    
    # Récupérer les détails du créatif
    ad_url = f"https://graph.facebook.com/v23.0/{ad_id}"
    params = {
        "access_token": FB_TOKEN,
        "fields": "name,creative{id,name,title,body,image_url,video_id,thumbnail_url,object_story_spec,instagram_permalink_url,effective_object_story_id}"
    }
    
    try:
        response = requests.get(ad_url, params=params)
        data = response.json()
        
        if 'error' in data:
            print(f"❌ Erreur API: {data['error'].get('message', 'Unknown error')}")
            continue
            
        print(f"✅ Annonce: {data.get('name', 'Sans nom')}")
        
        if 'creative' in data:
            creative = data['creative']
            print(f"  Creative ID: {creative.get('id', 'N/A')}")
            
            # Vérifier les différents types de médias
            if creative.get('video_id'):
                video_id = creative['video_id']
                print(f"  📹 VIDEO détectée!")
                print(f"     Video ID: {video_id}")
                print(f"     URL Facebook: https://www.facebook.com/{video_id}")
                
                # Essayer de récupérer plus d'infos sur la vidéo
                video_url = f"https://graph.facebook.com/v23.0/{video_id}"
                video_params = {
                    "access_token": FB_TOKEN,
                    "fields": "source,permalink_url,thumbnails"
                }
                video_response = requests.get(video_url, params=video_params)
                video_data = video_response.json()
                
                if 'source' in video_data:
                    print(f"     Source directe: {video_data['source'][:100]}...")
                if 'permalink_url' in video_data:
                    print(f"     Permalink: {video_data['permalink_url']}")
                    
            elif creative.get('image_url'):
                print(f"  🖼️  IMAGE détectée!")
                print(f"     URL: {creative['image_url'][:100]}...")
                
            elif creative.get('instagram_permalink_url'):
                print(f"  📱 INSTAGRAM détecté!")
                print(f"     URL: {creative['instagram_permalink_url']}")
                
            if creative.get('thumbnail_url'):
                print(f"  🖼️  Thumbnail: {creative['thumbnail_url'][:100]}...")
                
            # Afficher le story spec si disponible
            if creative.get('object_story_spec'):
                spec = creative['object_story_spec']
                if 'link_data' in spec:
                    link_data = spec['link_data']
                    if 'link' in link_data:
                        print(f"  🔗 Link: {link_data['link']}")
                        
        else:
            print("  ⚠️  Pas de creative trouvé")
            
    except Exception as e:
        print(f"❌ Erreur: {e}")

print("\n" + "=" * 80)
print("💡 Note: Les URLs de vidéos Facebook peuvent nécessiter une authentification")