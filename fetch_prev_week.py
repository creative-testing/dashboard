#!/usr/bin/env python3
"""
Fetch de la semaine PRÉCÉDENTE (12-18 août) pour comparaison semaine à semaine
"""
import os
import requests
import json
from dotenv import load_dotenv
from datetime import datetime
from collections import defaultdict
import time

load_dotenv()

def fetch_prev_week_data():
    """Récupère les données de la semaine précédente (12-18 août)"""
    
    token = os.getenv("FB_TOKEN")
    
    print("🚀 FETCH SEMAINE PRÉCÉDENTE (12-18 AOÛT)")
    print("=" * 70)
    print(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 1. Récupérer les comptes
    print("\n📊 Phase 1: Comptes...")
    accounts_url = "https://graph.facebook.com/v23.0/me/adaccounts"
    params = {
        "access_token": token,
        "fields": "id,name,account_status",
        "limit": 100
    }
    
    response = requests.get(accounts_url, params=params)
    accounts = response.json().get("data", [])
    active_accounts = [acc for acc in accounts if acc.get("account_status") == 1]
    account_names = {acc["id"]: acc.get("name", "Sans nom") for acc in active_accounts}
    
    print(f"✅ {len(active_accounts)} comptes actifs")
    
    # 2. Récupérer les insights pour la semaine précédente
    print("\n📊 Phase 2: Insights semaine précédente...")
    
    batch_requests = []
    
    for account_id in account_names.keys():
        filtering = '[{"field":"impressions","operator":"GREATER_THAN","value":"0"}]'
        # Date range spécifique : 12-18 août 2025
        time_range = '{"since":"2025-08-12","until":"2025-08-18"}'
        batch_requests.append({
            "method": "GET",
            "relative_url": f"{account_id}/insights?level=ad&time_range={time_range}&fields=ad_id,ad_name,campaign_name,adset_name,impressions,spend,clicks,ctr,cpm,reach,frequency,actions,action_values&limit=500&filtering={filtering}"
        })
    
    # Batch API
    batch_size = 50
    all_insights_results = []
    
    for i in range(0, len(batch_requests), batch_size):
        batch = batch_requests[i:i+batch_size]
        batch_url = "https://graph.facebook.com/v23.0/"
        batch_params = {
            "access_token": token,
            "batch": json.dumps(batch)
        }
        
        print(f"   Batch {i//batch_size + 1}/{(len(batch_requests)-1)//batch_size + 1}...", end="", flush=True)
        
        try:
            response = requests.post(batch_url, data=batch_params)
            batch_results = response.json()
            all_insights_results.extend(batch_results)
            print(" ✅")
        except Exception as e:
            print(f" ❌ {e}")
    
    # Traiter les insights
    insights_by_ad = {}
    ad_ids_by_account = defaultdict(list)
    
    for idx, result in enumerate(all_insights_results):
        if result.get("code") == 200:
            body = json.loads(result["body"])
            data = body.get("data", [])
            if idx < len(active_accounts):
                account_id = active_accounts[idx]["id"]
                
                for ad in data:
                    ad_id = ad.get("ad_id")
                    if ad_id:
                        ad_ids_by_account[account_id].append(ad_id)
                        insights_by_ad[ad_id] = ad
    
    total_ads = len(insights_by_ad)
    print(f"\n✅ {total_ads} annonces semaine précédente")
    
    # 3. Récupérer formats (même approche)
    print("\n📊 Phase 3: Formats...")
    creatives_by_ad = {}
    creative_batch_requests = []
    
    for ad_id in insights_by_ad.keys():
        creative_batch_requests.append({
            "method": "GET",
            "relative_url": f"{ad_id}?fields=creative{{video_id,image_url,instagram_permalink_url,object_story_spec}}"
        })
    
    print(f"   {len(creative_batch_requests)} creatives...")
    
    # Batch creatives
    for i in range(0, len(creative_batch_requests), batch_size):
        batch = creative_batch_requests[i:i+batch_size]
        batch_url = "https://graph.facebook.com/v23.0/"
        batch_params = {
            "access_token": token,
            "batch": json.dumps(batch)
        }
        
        print(f"   Batch {i//batch_size + 1}/{(len(creative_batch_requests)-1)//batch_size + 1}...", end="", flush=True)
        
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
    
    # 4. Traitement final (même logique que les autres)
    all_ads_data = []
    format_stats = defaultdict(int)
    
    for ad_id, insights in insights_by_ad.items():
        # Account
        account_name = "Unknown"
        for acc_id, ad_list in ad_ids_by_account.items():
            if ad_id in ad_list:
                account_name = account_names.get(acc_id, "Sans nom")
                break
        
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
            "account_name": account_name,
            "ad_name": insights.get("ad_name", "Sans nom"),
            "ad_id": ad_id,
            "format": format_type,
            "spend": spend,
            "impressions": impressions,
            "clicks": clicks,
            "ctr": ctr,
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
            "period": "previous_week",
            "date_range": "2025-08-12 to 2025-08-18",
            "total_ads": len(all_ads_data),
            "total_accounts": len(active_accounts),
            "ads_with_creative": len(creatives_by_ad)
        },
        "format_distribution": dict(format_stats),
        "ads": all_ads_data
    }
    
    filename = "hybrid_data_prev_week.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    # Résumé
    total_spend = sum(ad['spend'] for ad in all_ads_data)
    print(f"\n" + "=" * 70)
    print(f"📊 RÉSUMÉ SEMAINE PRÉCÉDENTE (12-18 AOÛT)")
    print(f"✅ {len(all_ads_data)} annonces")
    print(f"✅ ${total_spend:,.0f} MXN")
    print(f"✅ {len(creatives_by_ad)} avec formats")
    
    if format_stats:
        print(f"\n📈 FORMATS:")
        for fmt, count in sorted(format_stats.items(), key=lambda x: x[1], reverse=True):
            pct = (count/len(all_ads_data)*100) if len(all_ads_data) > 0 else 0
            print(f"  {fmt}: {count} ({pct:.1f}%)")
    
    print(f"\n💾 Sauvegardé: {filename}")
    return filename

if __name__ == "__main__":
    print("⚡ Fetch semaine précédente pour comparaison")
    print("📅 Période : 12-18 août 2025")
    
    start = time.time()
    filename = fetch_prev_week_data()
    elapsed = time.time() - start
    
    if filename:
        print(f"\n✨ Succès en {elapsed/60:.1f} minutes!")