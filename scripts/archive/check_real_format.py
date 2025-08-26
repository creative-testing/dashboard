#!/usr/bin/env python3
"""
Vérifie le format réel de quelques annonces connues.
"""

import requests
import os
from dotenv import load_dotenv

load_dotenv()
FB_TOKEN = os.getenv('FB_TOKEN')

# Annonces qu'on connaît
test_ads = [
    ("6867984162740", "RATON PEREZ CATY"),
    ("6820250028540", "BOTANICAL BLUE BOX IG"),
    ("6761146071028", "Video 2 - Preparando etiquetas"),
    ("6761153778828", "Video 3 - Preparando etiquetas"),
    ("6820282431340", "RATON PEREZ"),
]

print("🔍 Vérification des formats RÉELS depuis l'API:")
print("=" * 80)

for ad_id, ad_name in test_ads:
    print(f"\n📌 {ad_name}")
    print(f"   ID: {ad_id}")
    
    # Récupérer TOUS les champs possibles du créatif
    url = f"https://graph.facebook.com/v23.0/{ad_id}"
    params = {
        "access_token": FB_TOKEN,
        "fields": "creative{id,name,object_type,status,degrees_of_freedom_spec,object_story_spec,asset_feed_spec,body,branded_content_sponsor_page_id,bundle_folder_id,categorization_criteria,category_media_source,destination_set_id,dynamic_ad_voice,effective_instagram_media_id,effective_object_story_id,image_crops,image_hash,image_url,instagram_actor_id,instagram_permalink_url,instagram_story_id,interactive_components_spec,link_deep_link_url,link_destination_display_url,link_og_id,link_url,messenger_sponsored_message,name,object_id,object_store_url,object_story_id,object_type,object_url,place_page_set_id,platform_customizations,playable_asset_id,portrait_customizations,product_set_id,recommender_settings,source_instagram_media_id,status,template_url,template_url_spec,thumbnail_url,title,url_tags,use_page_actor_override,video_id}"
    }
    
    try:
        response = requests.get(url, params=params)
        data = response.json()
        
        if 'error' in data:
            print(f"   ❌ Erreur: {data['error'].get('message', 'Unknown')}")
            continue
            
        if 'creative' in data:
            creative = data['creative']
            
            # Afficher tous les champs qui nous intéressent
            print(f"   object_type: {creative.get('object_type', 'N/A')}")
            print(f"   video_id: {creative.get('video_id', 'N/A')}")
            print(f"   image_url: {'Oui' if creative.get('image_url') else 'Non'}")
            print(f"   instagram_permalink_url: {'Oui' if creative.get('instagram_permalink_url') else 'Non'}")
            
            # Analyser object_story_spec
            if creative.get('object_story_spec'):
                spec = creative['object_story_spec']
                print(f"   object_story_spec trouvé:")
                if spec.get('video_data'):
                    print(f"     - video_data: OUI → FORMAT VIDEO")
                if spec.get('link_data'):
                    link_data = spec['link_data']
                    if link_data.get('child_attachments'):
                        print(f"     - child_attachments: OUI → FORMAT CAROUSEL")
                    elif link_data.get('multi_share_optimized'):
                        print(f"     - multi_share_optimized: OUI → FORMAT CAROUSEL")
                    elif link_data.get('image_hash'):
                        print(f"     - image_hash: OUI → FORMAT IMAGE")
                if spec.get('photo_data'):
                    print(f"     - photo_data: OUI → FORMAT IMAGE")
                        
            # Déterminer le format final
            format_type = "UNKNOWN"
            if creative.get('object_type'):
                format_type = creative['object_type'].upper()
            elif creative.get('video_id'):
                format_type = "VIDEO"
            elif creative.get('object_story_spec', {}).get('video_data'):
                format_type = "VIDEO"
            elif creative.get('object_story_spec', {}).get('link_data', {}).get('child_attachments'):
                format_type = "CAROUSEL"
            elif creative.get('image_url'):
                format_type = "IMAGE"
            elif creative.get('instagram_permalink_url'):
                # Pour Instagram, on ne sait pas directement, ça peut être image, video ou carousel
                format_type = "INSTAGRAM_POST"
                
            print(f"   ✅ FORMAT DÉTERMINÉ: {format_type}")
            
    except Exception as e:
        print(f"   ❌ Erreur: {e}")