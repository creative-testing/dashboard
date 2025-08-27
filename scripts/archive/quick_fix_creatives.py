#!/usr/bin/env python3
"""
Fix RAPIDE avec approche ?ids= pour récupérer les creatives
Plus fiable que le batch API
"""
import os
import json
import requests
from dotenv import load_dotenv
import time

load_dotenv()

ACCESS_TOKEN = os.getenv("FACEBOOK_ACCESS_TOKEN")
if not ACCESS_TOKEN:
    raise SystemExit("FACEBOOK_ACCESS_TOKEN not set. Define it in .env")
GRAPH_URL = "https://graph.facebook.com/v23.0"

def fix_period(period):
    """Fix un seul fichier de période"""
    filename = f'hybrid_data_{period}d.json'
    
    print(f"\n🔧 Fix {filename}...")
    
    # Charger les données
    with open(filename, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    ads = data.get('ads', [])
    print(f"  📝 {len(ads)} ads à traiter")
    
    # Process par chunks de 20 (plus fiable)
    fixed_count = 0
    
    for i in range(0, len(ads), 20):  # Traiter TOUS les ads, pas juste 500
        chunk = ads[i:i+20]
        ad_ids = [ad['ad_id'] for ad in chunk if ad.get('ad_id')]
        
        if not ad_ids:
            continue
        
        ids_str = ",".join(ad_ids)
        
        # Utiliser l'approche ?ids= qui marche
        url = f"{GRAPH_URL}/"
        params = {
            "ids": ids_str,
            "fields": "creative{video_id,image_url,instagram_permalink_url}",
            "access_token": ACCESS_TOKEN
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                creatives_data = response.json()
                
                for ad in chunk:
                    ad_id = ad.get('ad_id')
                    if ad_id in creatives_data and 'creative' in creatives_data[ad_id]:
                        creative = creatives_data[ad_id]['creative']
                        
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
            
            # Petit delay pour éviter rate limit
            time.sleep(0.1)
            
        except Exception as e:
            print(f"  ⚠️ Erreur chunk {i}: {e}")
        
        # Progress
        if i % 100 == 0:
            print(f"  Progress: {i}/{len(ads)}")
    
    # Sauvegarder les changements
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"  ✅ {fixed_count} ads corrigés!")
    
    # Stats
    format_stats = {}
    for ad in ads:
        fmt = ad.get('format', 'UNKNOWN')
        format_stats[fmt] = format_stats.get(fmt, 0) + 1
    
    print(f"  📊 Formats totaux:")
    for fmt, count in format_stats.items():
        print(f"    {fmt}: {count}")
    
    return fixed_count

def main():
    """Fix rapide pour 7d seulement d'abord"""
    print("⚡ FIX RAPIDE CREATIVES - Approche ?ids=")
    print("=" * 60)
    
    # Commencer par 7d pour tester
    fixed = fix_period(7)
    
    if fixed > 0:
        print(f"\n🎉 Succès pour 7d! Continuer avec les autres...")
        # Si ça marche, faire les autres
        for period in [3, 14, 30]:
            if os.path.exists(f'hybrid_data_{period}d.json'):
                fix_period(period)
    
    print("\n✅ TERMINÉ!")

if __name__ == "__main__":
    main()
