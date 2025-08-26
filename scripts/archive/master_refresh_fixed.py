#!/usr/bin/env python3
"""
SCRIPT MASTER FINAL avec approche ?ids= pour creatives
Version corrigée et fiable
"""
import os
import requests
import json
from dotenv import load_dotenv
from datetime import datetime, timedelta
from collections import defaultdict
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

load_dotenv()

def get_reference_date():
    """Date référence : hier (journée complète)"""
    yesterday = datetime.now() - timedelta(days=1)
    return yesterday.strftime('%Y-%m-%d')

def calculate_period_dates(period_days, reference_date):
    """Calcule fenêtre période"""
    ref = datetime.strptime(reference_date, '%Y-%m-%d')
    end_date = ref
    start_date = ref - timedelta(days=period_days - 1)
    
    return start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')

def fetch_account_insights(account, token, since_date, until_date):
    """Fetch insights pour un compte"""
    account_id = account["id"]
    account_name = account.get("name", "Sans nom")
    
    try:
        url = f"https://graph.facebook.com/v23.0/{account_id}/insights"
        params = {
            "access_token": token,
            "level": "ad",
            "time_range": f'{{"since":"{since_date}","until":"{until_date}"}}',
            "fields": "ad_id,ad_name,campaign_name,adset_name,impressions,spend,clicks,ctr,cpm,reach,frequency,actions,action_values,cost_per_action_type",
            "filtering": '[{"field":"impressions","operator":"GREATER_THAN","value":"0"}]',
            "limit": 1000
        }
        
        # Pagination
        all_ads = []
        current_url = url
        page = 0
        
        while current_url and page < 30:
            if page == 0:
                response = requests.get(current_url, params=params)
            else:
                response = requests.get(current_url)
            
            data = response.json()
            
            if "data" in data:
                ads = data["data"]
                
                for ad in ads:
                    ad['account_name'] = account_name
                    ad['account_id'] = account_id
                
                all_ads.extend(ads)
                
                if "paging" in data and "next" in data["paging"]:
                    current_url = data["paging"]["next"]
                    page += 1
                else:
                    break
            else:
                break
        
        return all_ads
        
    except Exception as e:
        return []

def fetch_creatives_simple(ad_ids, token):
    """✅ Approche simple avec ?ids= (plus fiable)"""
    
    chunk_size = 50  # Limite conservative pour URL
    all_creatives = {}
    
    for i in range(0, len(ad_ids), chunk_size):
        chunk = ad_ids[i:i+chunk_size]
        ids_string = ",".join(chunk)
        
        try:
            # ✅ Requête simple et fiable
            url = "https://graph.facebook.com/v23.0/"
            params = {
                "access_token": token,
                "ids": ids_string,
                "fields": "creative{video_id,image_url,instagram_permalink_url}"
            }
            
            response = requests.get(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                
                if isinstance(data, dict):
                    # ✅ Parsing simple : {ad_id: {creative: ...}}
                    for ad_id, ad_data in data.items():
                        if isinstance(ad_data, dict) and "creative" in ad_data:
                            all_creatives[ad_id] = ad_data["creative"]
            
            # Petite pause pour éviter rate limiting
            time.sleep(0.1)
            
        except Exception as e:
            print(f"   ❌ Chunk {i//chunk_size + 1}: {e}")
    
    return all_creatives

def master_refresh_fixed():
    """Master refresh avec fetch creatives corrigé"""
    
    token = os.getenv("FB_TOKEN")
    reference_date = get_reference_date()
    
    print("🚀 MASTER REFRESH CORRIGÉ - ?ids= APPROACH")
    print("=" * 70)
    print(f"📅 Date référence: {reference_date}")
    print(f"🔧 Fix: ?ids= au lieu de batch pour creatives")
    
    start_master = time.time()
    
    # 1. Comptes
    print(f"\n📊 Comptes...")
    accounts_response = requests.get("https://graph.facebook.com/v23.0/me/adaccounts", params={
        "access_token": token,
        "fields": "id,name,account_status",
        "limit": 100
    })
    
    accounts = accounts_response.json().get("data", [])
    active_accounts = [acc for acc in accounts if acc.get("account_status") == 1]
    
    print(f"✅ {len(active_accounts)} comptes actifs")
    
    # 2. Refresh juste 7 jours pour test rapide
    period = 7
    since_date, until_date = calculate_period_dates(period, reference_date)
    
    print(f"\n🔄 TEST PÉRIODE 7J ({since_date} → {until_date})")
    print("-" * 50)
    
    # Insights parallèles
    print(f"   📊 Insights...")
    all_insights = []
    
    with ThreadPoolExecutor(max_workers=25) as executor:
        futures = [
            executor.submit(fetch_account_insights, acc, token, since_date, until_date)
            for acc in active_accounts
        ]
        
        for future in as_completed(futures):
            account_insights = future.result()
            all_insights.extend(account_insights)
    
    print(f"   ✅ {len(all_insights)} insights")
    
    # ✅ Creatives avec nouvelle approche
    print(f"   🎨 Creatives (?ids= approach)...")
    ad_ids = [ad.get("ad_id") for ad in all_insights if ad.get("ad_id")]
    
    start_creatives = time.time()
    creatives_by_ad = fetch_creatives_simple(ad_ids, token)
    creatives_time = time.time() - start_creatives
    
    print(f"   ✅ {len(creatives_by_ad)} creatives en {creatives_time:.1f}s")
    
    # Processing final
    processed_ads = []
    format_stats = defaultdict(int)
    
    for insights in all_insights:
        ad_id = insights.get("ad_id")
        if not ad_id:
            continue
        
        # ✅ Format detection avec nouveaux creatives
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
        
        # Métriques (même logique)
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
            "account_name": insights.get("account_name"),
            "ad_name": insights.get("ad_name"),
            "ad_id": ad_id,
            "campaign_name": insights.get("campaign_name", ""),
            "format": format_type,
            "spend": spend,
            "impressions": impressions,
            "clicks": clicks,
            "ctr": ctr,
            "cpm": cpm,
            "cpa": cpa,
            "reach": reach,
            "frequency": frequency,
            "purchases": purchases,
            "purchase_value": purchase_value,
            "roas": roas,
            "media_url": media_url
        }
        
        processed_ads.append(ad_data)
    
    # Sauvegarder
    output = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "reference_date": reference_date,
            "period_days": period,
            "date_range": f"{since_date} to {until_date}",
            "method": "ids_approach_fixed",
            "total_ads": len(processed_ads),
            "ads_with_creative": len(creatives_by_ad),
            "creative_success_rate": len(creatives_by_ad) / len(ad_ids) * 100 if ad_ids else 0
        },
        "format_distribution": dict(format_stats),
        "ads": processed_ads
    }
    
    filename = "data/current/hybrid_data_7d_fixed.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    # Résumé
    master_time = time.time() - start_master
    total_spend = sum(ad['spend'] for ad in processed_ads)
    
    print(f"\n" + "=" * 70)
    print(f"🎉 MASTER REFRESH CORRIGÉ TERMINÉ")
    print(f"⚡ Temps: {master_time:.1f}s")
    print(f"✅ {len(processed_ads)} ads, ${total_spend:,.0f} MXN")
    print(f"🎨 {len(creatives_by_ad)} creatives ({len(creatives_by_ad)/len(ad_ids)*100:.1f}% succès)")
    
    print(f"\n📊 FORMATS DÉTECTÉS:")
    for fmt, count in sorted(format_stats.items(), key=lambda x: x[1], reverse=True):
        pct = count / len(processed_ads) * 100 if processed_ads else 0
        print(f"  {fmt:12}: {count:4} ({pct:5.1f}%)")
    
    return output

if __name__ == "__main__":
    print("🔧 Test script master avec fix creatives")
    print("⚡ Approche ?ids= plus fiable")
    
    result = master_refresh_fixed()
    
    if result:
        print(f"\n✨ SUCCESS! Fix validé")
        print(f"🎯 Prêt pour intégrer dans production")