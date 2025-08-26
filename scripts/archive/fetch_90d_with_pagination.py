#!/usr/bin/env python3
"""
Refetch 90j AVEC pagination pour récupérer toutes les annonces
Corrige le problème des comptes manquants
"""
import os
import requests
import json
from dotenv import load_dotenv
from datetime import datetime
from collections import defaultdict
import time

load_dotenv()

def fetch_with_pagination(url, params, max_pages=10):
    """Fetch avec pagination pour récupérer toutes les données"""
    all_data = []
    current_url = url
    page = 0
    
    while current_url and page < max_pages:
        try:
            if page == 0:
                response = requests.get(current_url, params=params)
            else:
                response = requests.get(current_url)  # URL contient déjà les params
            
            data = response.json()
            
            if "data" in data:
                all_data.extend(data["data"])
                
                # Pagination
                if "paging" in data and "next" in data["paging"]:
                    current_url = data["paging"]["next"]
                    page += 1
                else:
                    break
            else:
                break
                
        except Exception as e:
            print(f"   ❌ Erreur pagination page {page}: {e}")
            break
    
    return all_data

def fetch_90d_corrected():
    """Fetch 90j avec pagination complète"""
    
    token = os.getenv("FB_TOKEN")
    
    print("🚀 FETCH 90J CORRIGÉ AVEC PAGINATION")
    print("=" * 70)
    
    # 1. Comptes
    print("📊 Phase 1: Comptes...")
    accounts_url = "https://graph.facebook.com/v23.0/me/adaccounts"
    accounts_params = {
        "access_token": token,
        "fields": "id,name,account_status",
        "limit": 100
    }
    
    accounts_data = fetch_with_pagination(accounts_url, accounts_params)
    active_accounts = [acc for acc in accounts_data if acc.get("account_status") == 1]
    account_names = {acc["id"]: acc.get("name", "Sans nom") for acc in active_accounts}
    
    print(f"✅ {len(active_accounts)} comptes actifs")
    
    # 2. Insights avec pagination par compte
    print("\n📊 Phase 2: Insights 90j avec pagination...")
    
    all_ads_insights = []
    
    for i, account in enumerate(active_accounts, 1):
        account_id = account["id"]
        account_name = account_names[account_id]
        
        print(f"   [{i}/{len(active_accounts)}] {account_name}...", end="", flush=True)
        
        # ✅ Utiliser time_range au lieu de date_preset pour éviter limitations
        insights_url = f"https://graph.facebook.com/v23.0/{account_id}/insights"
        insights_params = {
            "access_token": token,
            "level": "ad",
            "time_range": '{"since":"2025-05-28","until":"2025-08-25"}',  # 90 jours précis
            "fields": "ad_id,ad_name,campaign_name,adset_name,impressions,spend,clicks,ctr,cpm,reach,frequency,actions,action_values",
            "filtering": '[{"field":"impressions","operator":"GREATER_THAN","value":"0"}]',
            "limit": 1000  # Plus gros pour réduire la pagination
        }
        
        try:
            account_ads = fetch_with_pagination(insights_url, insights_params, max_pages=20)
            
            # Ajouter account info à chaque ad
            for ad in account_ads:
                ad['account_name'] = account_name
                ad['account_id'] = account_id
            
            all_ads_insights.extend(account_ads)
            print(f" ✅ {len(account_ads)} ads")
            
            # Petite pause pour éviter rate limiting
            if i < len(active_accounts):
                time.sleep(0.3)
                
        except Exception as e:
            print(f" ❌ {e}")
    
    print(f"\n✅ {len(all_ads_insights)} annonces au total avec insights")
    
    # 3. Creatives (même logique qu'avant)
    print("\n📊 Phase 3: Creatives...")
    
    creatives_by_ad = {}
    ad_ids = [ad.get("ad_id") for ad in all_ads_insights if ad.get("ad_id")]
    
    # Batch requests pour creatives
    batch_size = 50
    for i in range(0, len(ad_ids), batch_size):
        batch_ids = ad_ids[i:i+batch_size]
        
        creative_batch = []
        for ad_id in batch_ids:
            creative_batch.append({
                "method": "GET",
                "relative_url": f"{ad_id}?fields=creative{{video_id,image_url,instagram_permalink_url,object_story_spec}}"
            })
        
        batch_url = "https://graph.facebook.com/v23.0/"
        batch_params = {
            "access_token": token,
            "batch": json.dumps(creative_batch)
        }
        
        print(f"   Batch creatives {i//batch_size + 1}/{(len(ad_ids)-1)//batch_size + 1}...", end="", flush=True)
        
        try:
            response = requests.post(batch_url, data=batch_params)
            batch_results = response.json()
            
            for result in batch_results:
                if result.get("code") == 200:
                    body = json.loads(result["body"])
                    ad_id = body.get("id")
                    if ad_id and "creative" in body:
                        creatives_by_ad[ad_id] = body["creative"]
            
            print(" ✅")
            time.sleep(0.1)
            
        except Exception as e:
            print(f" ❌ {e}")
    
    print(f"\n✅ {len(creatives_by_ad)} creatives récupérés")
    
    # 4. Traitement final
    print("\n📊 Phase 4: Traitement...")
    
    all_ads_data = []
    format_stats = defaultdict(int)
    
    for insights in all_ads_insights:
        ad_id = insights.get("ad_id")
        if not ad_id:
            continue
            
        # Format
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
        
        all_ads_data.append(ad_data)
    
    # 5. Sauvegarder
    data = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "period_days": 90,
            "date_range": "2025-05-28 to 2025-08-25",
            "method": "time_range_with_pagination", 
            "total_ads": len(all_ads_data),
            "total_accounts": len(active_accounts),
            "ads_with_creative": len(creatives_by_ad)
        },
        "format_distribution": dict(format_stats),
        "ads": all_ads_data
    }
    
    filename = "hybrid_data_90d_corrected.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    # Résumé
    total_spend = sum(ad['spend'] for ad in all_ads_data)
    print(f"\n" + "=" * 70)
    print(f"📊 RÉSUMÉ 90J CORRIGÉ")
    print(f"✅ {len(all_ads_data)} annonces")
    print(f"✅ ${total_spend:,.0f} MXN") 
    print(f"✅ Méthode: time_range + pagination")
    
    # Top comptes
    account_spend = defaultdict(float)
    for ad in all_ads_data:
        account_spend[ad["account_name"]] += ad["spend"]
    
    print(f"\n💰 TOP 5 COMPTES:")
    for acc, spend in sorted(account_spend.items(), key=lambda x: x[1], reverse=True)[:5]:
        print(f"  {acc[:30]:30} ${spend:,.0f}")
    
    return filename

if __name__ == "__main__":
    print("⚡ Fetch 90j CORRIGÉ avec pagination")
    print("🎯 Objectif: récupérer TOUS les comptes manquants")
    
    start = time.time()
    filename = fetch_90d_corrected()
    elapsed = time.time() - start
    
    if filename:
        print(f"\n✨ Succès en {elapsed/60:.1f} minutes!")
        print(f"💾 Nouvelles données: {filename}")