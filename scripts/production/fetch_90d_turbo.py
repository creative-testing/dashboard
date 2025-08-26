#!/usr/bin/env python3
"""
FETCH 90J TURBO - Optimisé pour MacBook M1 Pro avec 64GB RAM
Parallélisation agressive pour récupérer toutes les données en 3-4 minutes
"""
import os
import requests
import json
from dotenv import load_dotenv
from datetime import datetime
from collections import defaultdict
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

load_dotenv()

# Thread-safe storage
lock = threading.Lock()
all_ads_insights = []
creatives_by_ad = {}

def fetch_account_insights(account, token):
    """Fetch insights pour un compte spécifique"""
    account_id = account["id"]
    account_name = account.get("name", "Sans nom")
    
    try:
        insights_url = f"https://graph.facebook.com/v23.0/{account_id}/insights"
        insights_params = {
            "access_token": token,
            "level": "ad",
            "time_range": '{"since":"2025-05-28","until":"2025-08-25"}',  # 90 jours précis
            "fields": "ad_id,ad_name,campaign_name,adset_name,impressions,spend,clicks,ctr,cpm,reach,frequency,actions,action_values",
            "filtering": '[{"field":"impressions","operator":"GREATER_THAN","value":"0"}]',
            "limit": 1000
        }
        
        # Pagination pour ce compte
        account_ads = []
        current_url = insights_url
        page = 0
        
        while current_url and page < 20:  # Max 20 pages par compte
            if page == 0:
                response = requests.get(current_url, params=insights_params)
            else:
                response = requests.get(current_url)
            
            data = response.json()
            
            if "data" in data:
                ads = data["data"]
                
                # Ajouter account info
                for ad in ads:
                    ad['account_name'] = account_name
                    ad['account_id'] = account_id
                
                account_ads.extend(ads)
                
                # Pagination
                if "paging" in data and "next" in data["paging"]:
                    current_url = data["paging"]["next"]
                    page += 1
                else:
                    break
            else:
                break
        
        # Thread-safe ajout
        with lock:
            all_ads_insights.extend(account_ads)
        
        return len(account_ads)
        
    except Exception as e:
        print(f"   ❌ {account_name}: {e}")
        return 0

def fetch_creative_batch(ad_ids_batch, token):
    """Fetch creatives pour un batch d'ad_ids"""
    
    creative_batch = []
    for ad_id in ad_ids_batch:
        creative_batch.append({
            "method": "GET",
            "relative_url": f"{ad_id}?fields=creative{{video_id,image_url,instagram_permalink_url,object_story_spec}}"
        })
    
    try:
        batch_url = "https://graph.facebook.com/v23.0/"
        batch_params = {
            "access_token": token,
            "batch": json.dumps(creative_batch)
        }
        
        response = requests.post(batch_url, data=batch_params)
        batch_results = response.json()
        
        batch_creatives = {}
        for result in batch_results:
            if result.get("code") == 200:
                body = json.loads(result["body"])
                ad_id = body.get("id")
                if ad_id and "creative" in body:
                    batch_creatives[ad_id] = body["creative"]
        
        # Thread-safe ajout
        with lock:
            creatives_by_ad.update(batch_creatives)
        
        return len(batch_creatives)
        
    except Exception as e:
        print(f"   ❌ Batch creative error: {e}")
        return 0

def fetch_90d_turbo():
    """Fetch 90j en mode TURBO avec parallélisation aggressive"""
    
    token = os.getenv("FB_TOKEN")
    
    print("🚀 FETCH 90J TURBO - PARALLÉLISATION AGGRESSIVE")
    print("=" * 70)
    print(f"💻 MacBook Pro M1 Pro - 10 cores, 64GB RAM")
    print(f"⚡ Workers: 20 en parallèle")
    
    start_time = time.time()
    
    # 1. Comptes
    print("\n📊 Phase 1: Comptes...")
    accounts_url = "https://graph.facebook.com/v23.0/me/adaccounts"
    accounts_params = {
        "access_token": token,
        "fields": "id,name,account_status",
        "limit": 100
    }
    
    response = requests.get(accounts_url, params=accounts_params)
    accounts = response.json().get("data", [])
    active_accounts = [acc for acc in accounts if acc.get("account_status") == 1]
    
    print(f"✅ {len(active_accounts)} comptes actifs")
    
    # 2. Insights en parallèle MASSIF
    print(f"\n📊 Phase 2: Insights en parallèle (20 workers)...")
    
    with ThreadPoolExecutor(max_workers=20) as executor:
        future_to_account = {
            executor.submit(fetch_account_insights, acc, token): acc 
            for acc in active_accounts
        }
        
        completed = 0
        for future in as_completed(future_to_account):
            account = future_to_account[future]
            try:
                ads_count = future.result()
                completed += 1
                print(f"   [{completed}/{len(active_accounts)}] {account.get('name', 'Unknown')[:25]:25} ✅ {ads_count} ads")
            except Exception as e:
                print(f"   ❌ {account.get('name', 'Error')}: {e}")
    
    insights_time = time.time()
    print(f"\n✅ {len(all_ads_insights)} annonces récupérées en {(insights_time-start_time)/60:.1f} min")
    
    # 3. Creatives en parallèle
    print(f"\n📊 Phase 3: Creatives en parallèle...")
    
    ad_ids = [ad.get("ad_id") for ad in all_ads_insights if ad.get("ad_id")]
    batch_size = 100  # Plus gros batch pour ton MacBook
    
    # Diviser en batchs
    ad_id_batches = [ad_ids[i:i+batch_size] for i in range(0, len(ad_ids), batch_size)]
    
    with ThreadPoolExecutor(max_workers=25) as executor:  # Encore plus de workers
        future_to_batch = {
            executor.submit(fetch_creative_batch, batch, token): i 
            for i, batch in enumerate(ad_id_batches)
        }
        
        completed = 0
        for future in as_completed(future_to_batch):
            batch_num = future_to_batch[future]
            try:
                creatives_count = future.result()
                completed += 1
                print(f"   Batch {completed}/{len(ad_id_batches)} ✅ {creatives_count} creatives")
            except Exception as e:
                print(f"   ❌ Batch {batch_num}: {e}")
    
    creatives_time = time.time()
    print(f"\n✅ {len(creatives_by_ad)} creatives en {(creatives_time-insights_time)/60:.1f} min")
    
    # 4. Traitement final (même logique)
    print(f"\n📊 Phase 4: Traitement...")
    
    final_ads_data = []
    format_stats = defaultdict(int)
    
    for insights in all_ads_insights:
        ad_id = insights.get("ad_id")
        if not ad_id:
            continue
            
        # Format detection
        format_type = "UNKNOWN"
        media_url = ""
        
        if ad_id in creatives_by_ad:
            creative = creatives_by_ad[ad_id]
            
            if creative.get("video_id"):
                format_type = "VIDEO"
                media_url = f"https://www.facebook.com/watch/?v={creative['video_id']}"
            elif creative.get("image_url"):
                format_type = "IMAGE"
                media_url = creative["image_url"]
            elif creative.get("instagram_permalink_url"):
                format_type = "INSTAGRAM"
                media_url = creative["instagram_permalink_url"]
        
        format_stats[format_type] += 1
        
        # Métriques
        spend = float(insights.get("spend", 0))
        impressions = int(insights.get("impressions", 0))
        clicks = int(insights.get("clicks", 0))
        ctr = float(insights.get("ctr", 0))
        cpm = float(insights.get("cpm", 0))
        reach = int(insights.get("reach", 0))
        frequency = float(insights.get("frequency", 0))
        
        # Conversions
        purchases = 0
        purchase_value = 0
        actions = insights.get("actions", [])
        action_values = insights.get("action_values", [])
        
        for action in actions:
            if action.get("action_type") in ["purchase", "omni_purchase"]:
                purchases = int(action.get("value", 0))
                break
        
        for action_value in action_values:
            if action_value.get("action_type") in ["purchase", "omni_purchase"]:
                purchase_value = float(action_value.get("value", 0))
                break
        
        roas = (purchase_value / spend) if spend > 0 else 0
        
        ad_data = {
            "account_name": insights.get("account_name", "Unknown"),
            "account_id": insights.get("account_id", ""),
            "ad_name": insights.get("ad_name", "Sans nom"),
            "ad_id": ad_id,
            "campaign_name": insights.get("campaign_name", ""),
            "format": format_type,
            "spend": spend,
            "impressions": impressions,
            "clicks": clicks,
            "ctr": ctr,
            "cpm": cpm,
            "reach": reach,
            "frequency": frequency,
            "purchases": purchases,
            "purchase_value": purchase_value,
            "roas": roas,
            "media_url": media_url
        }
        
        final_ads_data.append(ad_data)
    
    # 5. Sauvegarder
    output_data = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "period_days": 90,
            "date_range": "2025-05-28 to 2025-08-25",
            "method": "parallel_time_range_with_pagination", 
            "total_ads": len(final_ads_data),
            "total_accounts": len(active_accounts),
            "ads_with_creative": len(creatives_by_ad),
            "fetch_time_minutes": (time.time() - start_time) / 60
        },
        "format_distribution": dict(format_stats),
        "ads": final_ads_data
    }
    
    # Remplacer le fichier 90d
    with open('hybrid_data_90d.json', 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    # Résumé
    total_time = time.time() - start_time
    total_spend = sum(ad['spend'] for ad in final_ads_data)
    
    print(f"\n" + "=" * 70)
    print(f"🚀 FETCH 90J TURBO TERMINÉ")
    print(f"✅ {len(final_ads_data)} annonces")
    print(f"✅ ${total_spend:,.0f} MXN")
    print(f"⚡ Temps total: {total_time/60:.1f} minutes")
    print(f"🔥 Performance: {len(final_ads_data)/total_time*60:.0f} annonces/minute")
    
    # Top comptes pour vérifier
    account_spend = defaultdict(float)
    for ad in final_ads_data:
        account_spend[ad["account_name"]] += ad["spend"]
    
    print(f"\n💰 VÉRIFICATION - TOP 5:")
    for acc, spend in sorted(account_spend.items(), key=lambda x: x[1], reverse=True)[:5]:
        print(f"  {acc[:30]:30} ${spend:,.0f}")
    
    return len(final_ads_data)

if __name__ == "__main__":
    print("⚡ FETCH 90J TURBO")
    print("🎯 Objectif: < 5 minutes avec MacBook M1 Pro")
    print("🔥 Parallélisation: 20 workers + batch 100")
    print()
    
    result = fetch_90d_turbo()
    if result:
        print(f"\n🎉 Succès! {result} annonces récupérées")
        print("💾 Fichier: hybrid_data_90d.json (remplacé)")
        print("✅ Prêt pour dashboard!")