#!/usr/bin/env python3
"""
Script de récupération - Enrichit les métriques déjà sauvegardées avec les creatives
"""
import os
import json
import requests
import time
from dotenv import load_dotenv
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

def fetch_creatives_batch(ad_ids, token):
    """Récupérer les CREATIVES (status, format, media) par batch"""
    if not ad_ids:
        return {}
    
    # Préparer les requêtes batch
    batch_requests = []
    for ad_id in ad_ids[:50]:  # Max 50 par batch
        batch_requests.append({
            "method": "GET",
            "relative_url": f"{ad_id}?fields=status,effective_status,created_time,creative{{status,video_id,image_url,instagram_permalink_url,object_story_spec}}"
        })
    
    try:
        url = "https://graph.facebook.com/v23.0"
        params = {
            "access_token": token,
            "batch": json.dumps(batch_requests)
        }
        
        response = requests.post(url, data=params, timeout=60)
        
        if response.status_code != 200:
            logger.warning(f"Erreur batch creatives: {response.status_code}")
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
                    format_type = "CAROUSEL"  # Souvent c'est un carousel sur Instagram
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
        logger.error(f"Erreur batch creatives: {str(e)[:50]}")
        return {}

def enrich_ads_with_creatives(ads, token):
    """Enrichir les ads avec leurs creatives"""
    logger.info(f"🎨 Enrichissement de {len(ads)} ads avec creatives...")
    
    # Grouper les ads par batch de 50
    ad_ids = [ad['ad_id'] for ad in ads]
    enriched = 0
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        for i in range(0, len(ad_ids), 50):
            batch = ad_ids[i:i+50]
            futures.append(executor.submit(fetch_creatives_batch, batch, token))
        
        creative_data = {}
        for future in as_completed(futures):
            try:
                batch_result = future.result(timeout=60)
                creative_data.update(batch_result)
            except Exception as e:
                logger.warning(f"Erreur batch creative: {str(e)[:30]}")
    
    # Enrichir les ads
    for ad in ads:
        ad_id = ad['ad_id']
        if ad_id in creative_data:
            ad.update(creative_data[ad_id])
            enriched += 1
        else:
            # Valeurs par défaut
            ad['status'] = 'UNKNOWN'
            ad['effective_status'] = 'UNKNOWN'
            ad['format'] = 'UNKNOWN'
            ad['media_url'] = ''
            ad['creative_status'] = 'UNKNOWN'
    
    logger.info(f"✅ {enriched}/{len(ads)} ads enrichies avec creatives")
    return ads

def main():
    print("🔧 ENRICHISSEMENT DEPUIS BACKUP")
    print("=" * 70)
    
    token = os.getenv("FACEBOOK_ACCESS_TOKEN")
    if not token:
        logger.error("❌ Token non trouvé")
        return
    
    # Charger le backup
    backup_file = 'data/temp/metrics_backup.json'
    if not os.path.exists(backup_file):
        logger.error(f"❌ Fichier backup non trouvé: {backup_file}")
        return
    
    print(f"📂 Chargement de {backup_file}...")
    with open(backup_file, 'r', encoding='utf-8') as f:
        all_data = json.load(f)
    
    print(f"✅ {len(all_data)} ads chargées")
    
    # Enrichir avec les creatives
    print(f"\n🎨 Enrichissement avec creatives...")
    all_data = enrich_ads_with_creatives(all_data, token)
    
    # Sauvegarder le résultat enrichi
    os.makedirs('data/current', exist_ok=True)
    output_file = 'data/current/baseline_90d_daily.json'
    
    baseline = {
        'metadata': {
            'timestamp': datetime.now().isoformat(),
            'method': 'enrich_from_backup',
            'total_rows': len(all_data),
            'has_demographics': False,
            'has_creatives': True
        },
        'daily_ads': all_data
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(baseline, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Sauvegardé dans {output_file}")
    print(f"💾 {len(all_data)} ads enrichies avec creatives")

if __name__ == '__main__':
    main()