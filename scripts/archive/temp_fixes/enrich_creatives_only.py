#!/usr/bin/env python3
"""
Script pour enrichir SEULEMENT les creatives sur un baseline existant
Sans refaire tout le fetch des métriques
"""
import os
import sys
import json
import time
import logging
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

def fetch_creatives_batch(ad_ids, token):
    """Récupérer les creatives par batch de 50"""
    if not ad_ids:
        return {}
    
    base_url = "https://graph.facebook.com/v23.0"
    
    # Préparer les requêtes batch
    batch_requests = []
    for ad_id in ad_ids[:50]:  # Max 50 par batch
        batch_requests.append({
            "method": "GET",
            "relative_url": f"{ad_id}?fields=status,effective_status,created_time,creative{{status,video_id,image_url,instagram_permalink_url,object_story_spec}}"
        })
    
    try:
        params = {
            "access_token": token,
            "batch": json.dumps(batch_requests)
        }
        
        response = requests.post(base_url, data=params, timeout=60)
        
        if response.status_code != 200:
            logger.warning(f"Erreur batch: {response.status_code}")
            return {}
        
        results = {}
        batch_responses = response.json()
        
        for i, resp in enumerate(batch_responses):
            if resp.get("code") == 200:
                ad_data = json.loads(resp["body"])
                ad_id = ad_ids[i]
                
                # Extraire les infos
                creative = ad_data.get("creative", {})
                
                # Déterminer format et media_url
                format_type = "UNKNOWN"
                media_url = ""
                
                if creative.get("video_id"):
                    format_type = "VIDEO"
                    media_url = f"https://www.facebook.com/watch/?v={creative['video_id']}"
                elif creative.get("image_url"):
                    format_type = "IMAGE"
                    media_url = creative["image_url"]
                elif creative.get("instagram_permalink_url"):
                    format_type = "CAROUSEL"
                    media_url = creative["instagram_permalink_url"]
                elif creative.get("object_story_spec"):
                    # Chercher dans object_story_spec
                    story = creative.get("object_story_spec", {})
                    if story.get("video_data"):
                        format_type = "VIDEO"
                    elif story.get("link_data", {}).get("image_hash"):
                        format_type = "IMAGE"
                
                results[ad_id] = {
                    "status": ad_data.get("status", "UNKNOWN"),
                    "effective_status": ad_data.get("effective_status", "UNKNOWN"),
                    "format": format_type,
                    "media_url": media_url,
                    "creative_status": creative.get("status", "UNKNOWN")
                }
        
        return results
        
    except Exception as e:
        logger.error(f"Erreur batch: {str(e)[:50]}")
        return {}

def main():
    print("🎨 ENRICHISSEMENT DES CREATIVES UNIQUEMENT")
    print("=" * 70)
    
    token = os.getenv("FACEBOOK_ACCESS_TOKEN")
    if not token:
        logger.error("❌ Token non trouvé")
        sys.exit(1)
    
    # Charger le baseline existant
    baseline_path = 'data/current/baseline_90d_daily.json'
    if not os.path.exists(baseline_path):
        logger.error(f"❌ Fichier non trouvé: {baseline_path}")
        sys.exit(1)
    
    print(f"📖 Chargement du baseline...")
    with open(baseline_path, 'r', encoding='utf-8') as f:
        baseline = json.load(f)
    
    all_ads = baseline['daily_ads']
    print(f"✅ {len(all_ads)} ads à enrichir")
    
    # Extraire les ad_ids uniques
    unique_ad_ids = list(set(ad['ad_id'] for ad in all_ads))
    print(f"📊 {len(unique_ad_ids)} ads uniques")
    
    # Enrichir par batchs avec workers parallèles
    print(f"\n🚀 Enrichissement par batchs de 50...")
    enriched = 0
    total_batches = (len(unique_ad_ids) + 49) // 50
    print(f"   {total_batches} batchs à traiter")
    
    creative_data = {}
    
    with ThreadPoolExecutor(max_workers=10) as executor:  # Moins de workers pour éviter rate limit
        futures = []
        for i in range(0, len(unique_ad_ids), 50):
            batch = unique_ad_ids[i:i+50]
            futures.append(executor.submit(fetch_creatives_batch, batch, token))
            # Petit délai entre les soumissions
            time.sleep(0.1)
        
        completed_batches = 0
        for future in as_completed(futures):
            try:
                batch_result = future.result(timeout=60)
                creative_data.update(batch_result)
                completed_batches += 1
                if completed_batches % 10 == 0 or completed_batches == total_batches:
                    print(f"   Progress: {completed_batches}/{total_batches} batchs")
            except Exception as e:
                logger.warning(f"Erreur batch: {str(e)[:30]}")
                completed_batches += 1
    
    # Enrichir toutes les ads (pas juste les uniques)
    print(f"\n📝 Application des enrichissements...")
    formats_found = set()
    
    for ad in all_ads:
        ad_id = ad['ad_id']
        if ad_id in creative_data:
            ad.update(creative_data[ad_id])
            formats_found.add(creative_data[ad_id]['format'])
            enriched += 1
        else:
            # Valeurs par défaut si pas trouvé
            ad['status'] = ad.get('status', 'UNKNOWN')
            ad['effective_status'] = ad.get('effective_status', 'UNKNOWN')
            ad['format'] = ad.get('format', 'UNKNOWN')
            ad['media_url'] = ad.get('media_url', '')
            ad['creative_status'] = ad.get('creative_status', 'UNKNOWN')
    
    print(f"✅ {enriched}/{len(all_ads)} ads enrichies")
    print(f"🎨 Formats trouvés: {formats_found}")
    
    # Mettre à jour le metadata
    baseline['metadata']['has_creatives'] = True
    baseline['metadata']['creatives_enriched_at'] = datetime.now().isoformat()
    baseline['metadata']['formats_found'] = list(formats_found)
    
    # Sauvegarder
    print(f"\n💾 Sauvegarde du baseline enrichi...")
    with open(baseline_path, 'w', encoding='utf-8') as f:
        json.dump(baseline, f, indent=2, ensure_ascii=False)
    
    # Stats
    format_counts = {}
    for ad in all_ads:
        fmt = ad.get('format', 'UNKNOWN')
        format_counts[fmt] = format_counts.get(fmt, 0) + 1
    
    print(f"\n📊 Distribution des formats:")
    for fmt, count in sorted(format_counts.items(), key=lambda x: x[1], reverse=True):
        pct = (count / len(all_ads)) * 100
        print(f"   {fmt}: {count} ({pct:.1f}%)")
    
    print(f"\n✅ Terminé! Baseline enrichi avec les creatives")
    
    # Si on a des vrais formats, lancer la compression
    if 'IMAGE' in formats_found or 'VIDEO' in formats_found:
        print("\n🗜️ Lancement de la compression...")
        os.system("python scripts/transform_to_columnar.py")
        print("✅ Compression terminée")

if __name__ == '__main__':
    main()