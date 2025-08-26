#!/usr/bin/env python3
"""
Test avec des annonces qu'on sait actives.
"""

import requests
import os
from dotenv import load_dotenv

load_dotenv()
FB_TOKEN = os.getenv('FB_TOKEN')

# Annonces depuis notre CSV qu'on sait actives
known_ads = [
    ("6867984162740", "RATON PEREZ CATY", "KRAPEL"),
    ("6820250028540", "BOTANICAL BLUE BOX IG", "KRAPEL"),
    ("6761146071028", "Video 2 - Preparando etiquetas - Sin voz", "Zendio"),
    ("6761153778828", "Video 3 - Preparando etiquetas - Con Narración", "Zendio"),
    ("6820282431340", "RATON PEREZ", "KRAPEL"),
    ("6823711746340", "LUCY BOX", "KRAPEL"),
    ("6867372804740", "RATON PEREZ 2", "KRAPEL"),
    ("6873015543740", "POP STATIONERY CATY", "KRAPEL"),
    ("6761163894828", "Imágen #3 MultiLabel", "Zendio"),
    ("6836549899940", "POP STATIONERY BOX", "KRAPEL"),
]

results = []

for ad_id, ad_name, account in known_ads:
    print(f"\n🔍 {ad_name}")
    
    # Récupérer le créatif
    url = f"https://graph.facebook.com/v23.0/{ad_id}"
    params = {
        "access_token": FB_TOKEN,
        "fields": "creative{id,image_url,video_id,thumbnail_url,instagram_permalink_url}"
    }
    
    try:
        response = requests.get(url, params=params)
        data = response.json()
        
        if 'creative' in data:
            creative = data['creative']
            
            # Construire l'URL
            media_url = None
            media_type = None
            
            if creative.get('instagram_permalink_url'):
                media_url = creative['instagram_permalink_url']
                media_type = 'INSTAGRAM'
            elif creative.get('video_id'):
                video_id = creative['video_id']
                media_url = f"https://www.facebook.com/watch/?v={video_id}"
                media_type = 'VIDEO'
            elif creative.get('image_url'):
                media_url = creative['image_url']
                media_type = 'IMAGE'
            
            if media_url:
                results.append({
                    'name': ad_name,
                    'account': account,
                    'type': media_type,
                    'url': media_url
                })
                print(f"   ✅ {media_type}: {media_url[:80]}...")
            else:
                print(f"   ⚠️ Pas d'URL trouvée")
    except Exception as e:
        print(f"   ❌ Erreur: {e}")

print("\n" + "=" * 80)
print(f"✅ {len(results)} URLs trouvées sur {len(known_ads)} annonces")

# Afficher le code HTML à ajouter
if results:
    print("\n📝 Exemple de liens HTML pour le dashboard:")
    print("-" * 40)
    for r in results[:5]:
        if r['type'] == 'INSTAGRAM':
            icon = "📱"
        elif r['type'] == 'VIDEO':
            icon = "📹"
        else:
            icon = "🖼️"
        
        print(f'<a href="{r["url"]}" target="_blank" title="Ver {r["type"]}">{icon}</a>')