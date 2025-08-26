#!/usr/bin/env python3
"""
Fetch les périodes manquantes : 3 jours et 14 jours
Pour compléter la demande de Pablo : 3/7/14/30/90 jours
"""
import os
import requests
import json
from dotenv import load_dotenv
from datetime import datetime, timedelta
from collections import defaultdict
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

load_dotenv()

# Thread-safe storage
lock = threading.Lock()

def fetch_account_insights_period(account, token, since_date, until_date, period_name):
    """Fetch insights pour un compte et une période spécifique"""
    account_id = account["id"]
    account_name = account.get("name", "Sans nom")
    
    try:
        insights_url = f"https://graph.facebook.com/v23.0/{account_id}/insights"
        insights_params = {
            "access_token": token,
            "level": "ad",
            "time_range": f'{{"since":"{since_date}","until":"{until_date}"}}',
            "fields": "ad_id,ad_name,campaign_name,adset_name,impressions,spend,clicks,ctr,cpm,reach,frequency,actions,action_values,cost_per_action_type",
            "filtering": '[{"field":"impressions","operator":"GREATER_THAN","value":"0"}]',
            "limit": 1000
        }
        
        # Pagination
        account_ads = []
        current_url = insights_url
        page = 0
        
        while current_url and page < 20:
            if page == 0:
                response = requests.get(current_url, params=insights_params)
            else:
                response = requests.get(current_url)
            
            data = response.json()
            
            if "data" in data:
                ads = data["data"]
                
                for ad in ads:
                    ad['account_name'] = account_name
                    ad['account_id'] = account_id
                
                account_ads.extend(ads)
                
                if "paging" in data and "next" in data["paging"]:
                    current_url = data["paging"]["next"]
                    page += 1
                else:
                    break
            else:
                break
        
        return account_ads, len(account_ads)
        
    except Exception as e:
        print(f"   ❌ {account_name}: {e}")
        return [], 0

def fetch_period_data(period_days):
    """Fetch données pour une période spécifique"""
    
    token = os.getenv("FB_TOKEN")
    
    # Calculer les dates
    today = datetime.now()
    end_date = today - timedelta(days=1)  # Hier (journée complète)
    start_date = end_date - timedelta(days=period_days-1)
    
    since_str = start_date.strftime('%Y-%m-%d')
    until_str = end_date.strftime('%Y-%m-%d')
    
    print(f"🚀 FETCH {period_days} JOURS ({since_str} à {until_str})")
    print("=" * 60)
    
    # Comptes
    print("📊 Comptes...")
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
    
    # Insights parallèles
    print(f"📊 Insights parallèles...")
    
    all_insights = []
    
    with ThreadPoolExecutor(max_workers=15) as executor:
        futures = [
            executor.submit(fetch_account_insights_period, acc, token, since_str, until_str, f"{period_days}d")
            for acc in active_accounts
        ]
        
        completed = 0
        for future in as_completed(futures):
            try:
                account_ads, count = future.result()
                all_insights.extend(account_ads)
                completed += 1
                print(f"   [{completed}/{len(active_accounts)}] ✅ {count} ads")
            except Exception as e:
                print(f"   ❌ Erreur: {e}")
    
    print(f"✅ {len(all_insights)} annonces récupérées")
    
    # Creatives (version simplifiée pour speed)
    print(f"📊 Creatives batch...")
    
    creatives_by_ad = {}
    ad_ids = [ad.get("ad_id") for ad in all_insights if ad.get("ad_id")]
    
    # Batch creatives
    batch_size = 100
    for i in range(0, len(ad_ids), batch_size):
        batch_ids = ad_ids[i:i+batch_size]
        
        batch_requests = []
        for ad_id in batch_ids:
            batch_requests.append({
                "method": "GET",
                "relative_url": f"{ad_id}?fields=creative{{video_id,image_url,instagram_permalink_url}}"
            })
        
        try:
            batch_url = "https://graph.facebook.com/v23.0/"
            batch_params = {
                "access_token": token,
                "batch": json.dumps(batch_requests)
            }
            
            response = requests.post(batch_url, data=batch_params)
            results = response.json()
            
            for result in results:
                if result.get("code") == 200:
                    body = json.loads(result["body"])
                    ad_id = body.get("id")
                    if ad_id and "creative" in body:
                        creatives_by_ad[ad_id] = body["creative"]
            
        except Exception as e:
            print(f"   ❌ Batch {i//batch_size}: {e}")
    
    # Traitement final
    processed_ads = []
    format_stats = defaultdict(int)
    
    for insights in all_insights:
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
        
        # Métriques + CPA pour Pablo
        spend = float(insights.get("spend", 0))
        impressions = int(insights.get("impressions", 0))
        clicks = int(insights.get("clicks", 0))
        ctr = float(insights.get("ctr", 0))
        cpm = float(insights.get("cpm", 0))
        
        # Extraire CPA depuis cost_per_action_type
        cpa = 0
        cost_per_actions = insights.get("cost_per_action_type", [])
        for cpa_item in cost_per_actions:
            if cpa_item.get("action_type") in ["purchase", "omni_purchase"]:
                cpa = float(cpa_item.get("value", 0))
                break
        
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
            "ad_name": insights.get("ad_name", "Sans nom"),
            "ad_id": ad_id,
            "campaign_name": insights.get("campaign_name", ""),
            "format": format_type,
            "spend": spend,
            "impressions": impressions,
            "clicks": clicks,
            "ctr": ctr,
            "cpm": cpm,
            "cpa": cpa,  # ✅ CPA ajouté pour Pablo
            "purchases": purchases,
            "purchase_value": purchase_value,  # ✅ Valor conversión
            "roas": roas,
            "media_url": media_url
        }
        
        processed_ads.append(ad_data)
    
    # Sauvegarder
    output = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "period_days": period_days,
            "date_range": f"{since_str} to {until_str}",
            "total_ads": len(processed_ads),
            "total_accounts": len(active_accounts),
            "ads_with_creative": len(creatives_by_ad)
        },
        "format_distribution": dict(format_stats),
        "ads": processed_ads
    }
    
    # Sauvegarder avec nom standard
    filename = f"hybrid_data_{period_days}d.json"
    filepath = f"data/current/{filename}"
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    total_spend = sum(ad['spend'] for ad in processed_ads)
    print(f"✅ {len(processed_ads)} ads, ${total_spend:,.0f} MXN")
    print(f"💾 Sauvegardé: {filepath}")
    
    return output

def fetch_missing_periods():
    """Fetch les périodes manquantes : 3j et 14j"""
    
    periods_to_fetch = [3, 14]  # Pablo veut 3/7/14/30/90
    
    for period in periods_to_fetch:
        start_time = time.time()
        
        try:
            data = fetch_period_data(period)
            elapsed = time.time() - start_time
            
            print(f"⚡ {period}j terminé en {elapsed/60:.1f} min")
            print()
            
        except Exception as e:
            print(f"❌ Erreur {period}j: {e}")

if __name__ == "__main__":
    print("⚡ FETCH PÉRIODES MANQUANTES POUR PABLO")
    print("🎯 Demande: 3/7/14/30/90 jours (on a déjà 7/30/90)")
    print("📊 À fetcher: 3j et 14j")
    print()
    
    fetch_missing_periods()
    
    print("✅ Toutes les périodes disponibles pour Pablo !")