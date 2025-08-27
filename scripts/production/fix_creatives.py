#!/usr/bin/env python3
"""
Fix rapide : Récupérer JUSTE les creatives qui manquent
et mettre à jour les fichiers JSON existants
"""
import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

ACCESS_TOKEN = os.getenv("FACEBOOK_ACCESS_TOKEN")
GRAPH_URL = "https://graph.facebook.com/v23.0"

def fetch_creatives_for_ads(ad_ids):
    """Récupère les creatives par batch pour une liste d'ad_ids"""
    creatives = {}
    
    # Process par chunks de 50
    for i in range(0, len(ad_ids), 50):
        chunk = ad_ids[i:i+50]
        ids_str = ",".join(chunk)
        
        url = f"{GRAPH_URL}/"
        params = {
            "ids": ids_str,
            "fields": "creative{video_id,image_url,instagram_permalink_url,object_story_spec}",
            "access_token": ACCESS_TOKEN
        }
        
        response = requests.get(url, params=params)
        
        if response.status_code == 200:
            data = response.json()
            for ad_id, ad_data in data.items():
                if "creative" in ad_data:
                    creatives[ad_id] = ad_data["creative"]
    
    return creatives

def fix_json_file(filename):
    """Corrige un fichier JSON en ajoutant les media_url et formats"""
    print(f"\n📊 Fix {filename}...")
    
    # Charger les données existantes
    with open(filename, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    ads = data.get('ads', [])
    if not ads:
        print(f"  ⚠️ Pas d'ads dans {filename}")
        return
    
    # Extraire tous les ad_ids
    ad_ids = [ad['ad_id'] for ad in ads if ad.get('ad_id')]
    print(f"  📝 {len(ad_ids)} ads à traiter")
    
    # Récupérer les creatives
    print(f"  🔄 Récupération des creatives...")
    creatives = fetch_creatives_for_ads(ad_ids)
    print(f"  ✅ {len(creatives)} creatives récupérés")
    
    # Mettre à jour chaque ad
    fixed_count = 0
    for ad in ads:
        ad_id = ad.get('ad_id')
        if ad_id in creatives:
            creative = creatives[ad_id]
            
            # Déterminer format et media_url
            if creative.get("video_id"):
                ad['format'] = "VIDEO"
                ad['media_url'] = f"https://www.facebook.com/watch/?v={creative['video_id']}"
                fixed_count += 1
            elif creative.get("image_url"):
                ad['format'] = "IMAGE"
                ad['media_url'] = creative["image_url"]
                fixed_count += 1
            elif creative.get("instagram_permalink_url"):
                ad['format'] = "INSTAGRAM"
                ad['media_url'] = creative["instagram_permalink_url"]
                fixed_count += 1
    
    # Mettre à jour metadata
    if 'metadata' in data:
        data['metadata']['creatives_fetched'] = len(creatives)
        data['metadata']['formats_fixed'] = fixed_count
    
    # Sauvegarder
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"  🎉 {fixed_count} ads corrigés avec media_url et format!")
    
    # Stats finales
    format_stats = {}
    for ad in ads:
        fmt = ad.get('format', 'UNKNOWN')
        format_stats[fmt] = format_stats.get(fmt, 0) + 1
    
    print(f"  📊 Distribution finale:")
    for fmt, count in format_stats.items():
        pct = count * 100 / len(ads)
        print(f"    {fmt}: {count} ({pct:.1f}%)")

def main():
    """Fix tous les fichiers JSON"""
    print("🔧 FIX CREATIVES - Récupération des media_url manquants")
    print("=" * 60)
    
    files_to_fix = [
        'hybrid_data_3d.json',
        'hybrid_data_7d.json', 
        'hybrid_data_14d.json',
        'hybrid_data_30d.json',
        'hybrid_data_90d.json'
    ]
    
    for filename in files_to_fix:
        if os.path.exists(filename):
            fix_json_file(filename)
        else:
            print(f"⚠️ {filename} non trouvé")
    
    print("\n✅ FIX TERMINÉ !")

if __name__ == "__main__":
    main()