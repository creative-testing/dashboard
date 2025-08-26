#!/usr/bin/env python3
"""
Test de l'approche ?ids= pour récupérer les creatives
Alternative plus simple au batch API
"""
import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

def test_ids_approach():
    """Test l'approche ?ids= vs batch API"""
    
    token = os.getenv("FB_TOKEN")
    
    # Prendre quelques ad_ids des nouvelles données
    with open('data/current/hybrid_data_7d.json') as f:
        data = json.load(f)
    
    # Échantillon d'ad_ids
    test_ad_ids = [ad['ad_id'] for ad in data['ads'][:10] if ad.get('ad_id')]
    
    print("🧪 TEST APPROCHE ?ids= pour CREATIVES")
    print("=" * 50)
    print(f"Test avec {len(test_ad_ids)} ad_ids")
    
    # Diviser en chunks (limite URL)
    chunk_size = 50  # Limite conservative
    all_creatives = {}
    
    for i in range(0, len(test_ad_ids), chunk_size):
        chunk = test_ad_ids[i:i+chunk_size]
        ids_string = ",".join(chunk)
        
        print(f"\n📡 Chunk {i//chunk_size + 1}: {len(chunk)} ids...")
        
        try:
            # ✅ Approche simple avec ?ids=
            url = "https://graph.facebook.com/v23.0/"
            params = {
                "access_token": token,
                "ids": ids_string,
                "fields": "creative{video_id,image_url,instagram_permalink_url}"
            }
            
            response = requests.get(url, params=params)
            print(f"   Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"   Type response: {type(data)}")
                
                if isinstance(data, dict):
                    print(f"   Keys trouvées: {len(data)} ad_ids")
                    
                    # Parser chaque ad
                    for ad_id, ad_data in data.items():
                        if isinstance(ad_data, dict):
                            # Vérifier qu'on a bien un creative
                            if "creative" in ad_data:
                                creative = ad_data["creative"]
                                
                                # Déterminer format
                                format_type = "UNKNOWN"
                                media_url = ""
                                
                                if creative.get("video_id"):
                                    format_type = "VIDEO"
                                    media_url = f"https://www.facebook.com/watch/?v={creative['video_id']}"
                                elif creative.get("image_url"):
                                    format_type = "IMAGE" 
                                    media_url = creative["image_url"]
                                elif creative.get("instagram_permalink_url"):
                                    format_type = "INSTAGRAM"
                                    media_url = creative["instagram_permalink_url"]
                                
                                all_creatives[ad_id] = {
                                    "format": format_type,
                                    "media_url": media_url,
                                    "creative": creative
                                }
                                
                                print(f"     ✅ {ad_id}: {format_type}")
                            else:
                                print(f"     ❌ {ad_id}: Pas de creative")
                        else:
                            print(f"     ⚠️  {ad_id}: Type inattendu {type(ad_data)}")
                else:
                    print(f"   ❌ Response pas un dict: {data}")
            else:
                print(f"   ❌ HTTP Error: {response.status_code}")
                print(f"   Response: {response.text[:200]}")
                
        except Exception as e:
            print(f"   ❌ Exception: {e}")
    
    print(f"\n" + "=" * 50)
    print(f"📊 RÉSULTAT TEST ?ids=")
    print(f"✅ Creatives récupérés: {len(all_creatives)}")
    
    # Stats par format
    format_counts = {}
    for creative_data in all_creatives.values():
        fmt = creative_data["format"]
        format_counts[fmt] = format_counts.get(fmt, 0) + 1
    
    print(f"📈 Distribution:")
    for fmt, count in format_counts.items():
        print(f"  {fmt}: {count}")
    
    print(f"\n💡 COMPARAISON:")
    print(f"  🔧 Batch API: Problèmes dict/list, debug complexe")
    print(f"  ✅ ?ids= API: Simple, prévisible, {len(all_creatives)} succès")
    
    if len(all_creatives) > 0:
        print(f"\n🎯 RECOMMANDATION: Utiliser ?ids= pour production!")
        
        # Exemple d'intégration 
        print(f"\n📝 Code production:")
        print(f"def fetch_creatives_simple(ad_ids, token):")
        print(f"    chunk_size = 50")
        print(f"    for chunk in chunks(ad_ids, chunk_size):")
        print(f"        response = GET /?ids={{','.join(chunk)}}&fields=creative{{...}}")
        print(f"        creatives.update(response.json())")
    
    return all_creatives

if __name__ == "__main__":
    print("🧪 Test alternative ?ids= pour creatives")
    print("🎯 Objectif: Méthode plus fiable que batch API")
    
    creatives = test_ids_approach()
    
    if creatives:
        print(f"\n✨ SUCCESS! Approche ?ids= fonctionne")
        print(f"🚀 Prêt pour implémentation production")