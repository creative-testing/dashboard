#!/usr/bin/env python3
"""
REFETCH COHÉRENT de toutes les périodes avec date de référence fixe
Fix définitif pour les incohérences de dates
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

# 🗓️ CONFIGURATION COHÉRENTE
REFERENCE_DATE = "2025-08-25"  # Dernière journée complète (dimanche)
PERIODS = [3, 7, 14, 30, 90]   # Demande de Pablo

# Thread-safe storage
lock = threading.Lock()

def calculate_period_dates(period_days, reference_date):
    """Calcule les dates pour une période donnée"""
    ref = datetime.strptime(reference_date, '%Y-%m-%d')
    end_date = ref
    start_date = ref - timedelta(days=period_days - 1)
    
    return start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')

def fetch_account_period(account, token, since_date, until_date, period_name):
    """Fetch optimisé pour un compte et une période"""
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
        
        # Pagination complète
        account_ads = []
        current_url = insights_url
        page = 0
        
        while current_url and page < 20:
            if page == 0:
                response = requests.get(current_url, params=insights_params)
            else:
                response = requests.get(current_url)
            
            data = response.json()
            
            if "data" in data and len(data["data"]) > 0:
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
        
        return account_ads
        
    except Exception as e:
        print(f"   ❌ {account_name[:20]}: {e}")
        return []

def fetch_creatives_batch(ad_ids_chunk, token):
    """Fetch creatives pour un chunk d'ad_ids"""
    
    batch_requests = []
    for ad_id in ad_ids_chunk:
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
        batch_results = response.json()
        
        creatives = {}
        for result in batch_results:
            if result.get("code") == 200:
                body = json.loads(result["body"])
                ad_id = body.get("id")
                if ad_id and "creative" in body:
                    creatives[ad_id] = body["creative"]
        
        return creatives
        
    except Exception as e:
        print(f"   ❌ Batch creative error: {e}")
        return {}

def refresh_period_coherent(period_days):
    """Refresh une période avec dates cohérentes"""
    
    token = os.getenv("FB_TOKEN")
    
    since_date, until_date = calculate_period_dates(period_days, REFERENCE_DATE)
    
    print(f"🚀 REFRESH {period_days}J COHÉRENT ({since_date} → {until_date})")
    print("=" * 60)
    
    start_time = time.time()
    
    # 1. Comptes
    accounts_url = "https://graph.facebook.com/v23.0/me/adaccounts"
    response = requests.get(accounts_url, params={
        "access_token": token,
        "fields": "id,name,account_status",
        "limit": 100
    })
    
    accounts = response.json().get("data", [])
    active_accounts = [acc for acc in accounts if acc.get("account_status") == 1]
    
    print(f"📊 {len(active_accounts)} comptes actifs")
    
    # 2. Insights parallèles
    all_insights = []
    
    with ThreadPoolExecutor(max_workers=20) as executor:  # Optimisé pour ton M1 Pro
        futures = [
            executor.submit(fetch_account_period, acc, token, since_date, until_date, f"{period_days}d")
            for acc in active_accounts
        ]
        
        for future in as_completed(futures):
            try:
                account_ads = future.result()
                all_insights.extend(account_ads)
            except Exception as e:
                print(f"   ❌ Future error: {e}")
    
    print(f"✅ {len(all_insights)} annonces récupérées")
    
    # 3. Creatives en parallèle  
    ad_ids = [ad.get("ad_id") for ad in all_insights if ad.get("ad_id")]
    creatives_by_ad = {}
    
    # Chunks pour creatives
    chunk_size = 100
    ad_id_chunks = [ad_ids[i:i+chunk_size] for i in range(0, len(ad_ids), chunk_size)]
    
    with ThreadPoolExecutor(max_workers=25) as executor:
        creative_futures = [
            executor.submit(fetch_creatives_batch, chunk, token)
            for chunk in ad_id_chunks
        ]
        
        for future in as_completed(creative_futures):
            try:
                chunk_creatives = future.result()
                creatives_by_ad.update(chunk_creatives)
            except Exception as e:
                print(f"   ❌ Creative future error: {e}")
    
    print(f"✅ {len(creatives_by_ad)} creatives récupérés")
    
    # 4. Processing final
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
        
        # Métriques complètes pour Pablo
        spend = float(insights.get("spend", 0))
        impressions = int(insights.get("impressions", 0))
        clicks = int(insights.get("clicks", 0))
        ctr = float(insights.get("ctr", 0))
        cpm = float(insights.get("cpm", 0))
        reach = int(insights.get("reach", 0))
        frequency = float(insights.get("frequency", 0))
        
        # CPA pour Pablo
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
            "cpa": cpa,  # ✅ Pour Pablo
            "reach": reach,
            "frequency": frequency,
            "purchases": purchases,
            "purchase_value": purchase_value,  # ✅ Valor conversión
            "roas": roas,
            "media_url": media_url
        }
        
        processed_ads.append(ad_data)
    
    # 5. Sauvegarder avec métadonnées cohérentes
    output = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "period_days": period_days,
            "reference_date": REFERENCE_DATE,
            "date_range": f"{since_date} to {until_date}",
            "method": "coherent_time_range_with_pagination",
            "total_ads": len(processed_ads),
            "total_accounts": len(active_accounts),
            "ads_with_creative": len(creatives_by_ad)
        },
        "format_distribution": dict(format_stats),
        "ads": processed_ads
    }
    
    # Sauvegarder
    filename = f"data/current/hybrid_data_{period_days}d.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    total_spend = sum(ad['spend'] for ad in processed_ads)
    elapsed = time.time() - start_time
    
    print(f"✅ {period_days}j: {len(processed_ads)} ads, ${total_spend:,.0f} MXN en {elapsed:.1f}s")
    
    return output

def refresh_all_periods():
    """Refresh toutes les périodes avec cohérence"""
    
    print("🗓️ REFRESH COHÉRENT TOUTES PÉRIODES")
    print("=" * 70)
    print(f"📅 Date de référence: {REFERENCE_DATE}")
    print(f"📊 Périodes: {PERIODS}")
    
    start_total = time.time()
    results = {}
    
    for period in PERIODS:
        try:
            data = refresh_period_coherent(period)
            results[period] = data
            time.sleep(0.5)  # Pause entre périodes
            
        except Exception as e:
            print(f"❌ Erreur {period}j: {e}")
    
    total_time = time.time() - start_total
    
    print(f"\n" + "=" * 70)
    print(f"🎉 REFRESH COHÉRENT TERMINÉ en {total_time/60:.1f} min")
    
    # Vérification cohérence
    print(f"\n🔍 VÉRIFICATION COHÉRENCE:")
    for period in PERIODS:
        if period in results:
            data = results[period]
            since, until = calculate_period_dates(period, REFERENCE_DATE)
            print(f"  ✅ {period:2}j: {since} → {until} ({data['metadata']['total_ads']} ads)")
    
    return results

if __name__ == "__main__":
    print("⚡ REFRESH COHÉRENT pour Pablo")
    print("🎯 Objectif: Données comparables avec date référence fixe")
    print(f"📅 Toutes périodes finissent le {REFERENCE_DATE}")
    print()
    
    results = refresh_all_periods()
    
    if results:
        print(f"\n✅ Données cohérentes prêtes pour dashboard !")
        print(f"📊 Périodes disponibles: {list(results.keys())}")
        print(f"🎯 Plus d'incohérences de dates !")