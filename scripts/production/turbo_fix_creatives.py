#!/usr/bin/env python3
"""
TURBO FIX - Version ultra-rapide avec parallélisation
"""
import os
import json
import requests
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor
import time
import argparse

load_dotenv()

ACCESS_TOKEN = os.getenv("FACEBOOK_ACCESS_TOKEN")
if not ACCESS_TOKEN:
    raise SystemExit("FACEBOOK_ACCESS_TOKEN not set. Define it in .env")
GRAPH_URL = "https://graph.facebook.com/v23.0"

def fetch_chunk_creatives(ad_ids):
    """Fetch creatives pour un chunk d'ads"""
    if not ad_ids:
        return {}
    
    ids_str = ",".join(ad_ids)
    url = f"{GRAPH_URL}/"
    params = {
        "ids": ids_str,
        "fields": "creative{video_id,image_url,instagram_permalink_url}",
        "access_token": ACCESS_TOKEN
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            return response.json()
    except:
        pass
    
    return {}

def fix_period_turbo(period, base_dir="."):
    """Fix turbo avec parallélisation"""
    filename = os.path.join(base_dir, f'hybrid_data_{period}d.json')
    
    print(f"\n⚡ TURBO FIX {filename}...")
    
    # Charger les données
    with open(filename, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    ads = data.get('ads', [])
    print(f"  📝 {len(ads)} ads à traiter")
    
    # Créer les chunks (50 ads par chunk pour efficacité)
    chunks = []
    for i in range(0, len(ads), 50):
        chunk = ads[i:i+50]
        ad_ids = [ad['ad_id'] for ad in chunk if ad.get('ad_id')]
        if ad_ids:
            chunks.append((i, chunk, ad_ids))
    
    print(f"  🚀 {len(chunks)} chunks à traiter en parallèle")
    
    # Parallélisation agressive (20 workers)
    fixed_count = 0
    with ThreadPoolExecutor(max_workers=20) as executor:
        # Lancer tous les fetchs en parallèle
        futures = [(i, chunk, executor.submit(fetch_chunk_creatives, ad_ids)) 
                   for i, chunk, ad_ids in chunks]
        
        # Récupérer les résultats au fur et à mesure
        for idx, (i, chunk, future) in enumerate(futures):
            try:
                creatives_data = future.result(timeout=30)
                
                # Appliquer les résultats
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
                
                # Progress
                if idx % 10 == 0:
                    print(f"    Progress: {idx}/{len(chunks)} chunks")
                    
            except Exception as e:
                print(f"    ⚠️ Erreur chunk {i}: {e}")
    
    # Sauvegarder
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    # Stats finales
    format_stats = {}
    media_count = 0
    for ad in ads:
        fmt = ad.get('format', 'UNKNOWN')
        format_stats[fmt] = format_stats.get(fmt, 0) + 1
        if ad.get('media_url'):
            media_count += 1
    
    print(f"  ✅ {fixed_count} ads corrigés")
    print(f"  📊 {media_count}/{len(ads)} ads avec media_url ({media_count*100//len(ads)}%)")
    print(f"  📊 Distribution formats:")
    for fmt, count in sorted(format_stats.items()):
        pct = count * 100 // len(ads)
        print(f"    {fmt}: {count} ({pct}%)")
    
    return fixed_count

def main():
    """Turbo fix toutes les périodes"""
    parser = argparse.ArgumentParser(description="Turbo fix creatives to populate media_url fast")
    parser.add_argument("--dir", dest="base_dir", default=".", help="Répertoire des JSON (par défaut: .)")
    args = parser.parse_args()

    base_dir = args.base_dir

    print("⚡⚡⚡ TURBO FIX CREATIVES - Ultra rapide")
    print("=" * 60)
    print(f"📂 Répertoire: {os.path.abspath(base_dir)}")

    periods = [7, 3, 14, 30, 90]

    start = time.time()
    total_fixed = 0

    for period in periods:
        path = os.path.join(base_dir, f'hybrid_data_{period}d.json')
        if os.path.exists(path):
            fixed = fix_period_turbo(period, base_dir=base_dir)
            total_fixed += fixed

    elapsed = time.time() - start
    print(f"\n🎉 TOTAL: {total_fixed} ads corrigés en {elapsed:.1f} secondes!")
    if elapsed > 0:
        print(f"⚡ Performance: {total_fixed/elapsed:.0f} ads/seconde")

if __name__ == "__main__":
    main()
