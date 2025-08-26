#!/usr/bin/env python3
"""
Fetch des données pour 3 périodes : 7, 30 et 90 jours
Version optimisée qui récupère tout en parallèle
"""
import os
import requests
import json
from dotenv import load_dotenv
from datetime import datetime
from collections import defaultdict
import time
import concurrent.futures

load_dotenv()

def fetch_period_data(period_days):
    """Récupère les données pour une période spécifique"""
    
    token = os.getenv("FB_TOKEN")
    
    print(f"\n📊 Fetch pour {period_days} jours...")
    
    # Déterminer le date_preset selon la période
    if period_days <= 7:
        date_preset = "last_7d"
    elif period_days <= 14:
        date_preset = "last_14d"
    elif period_days <= 30:
        date_preset = "last_30d"
    elif period_days <= 90:
        date_preset = "last_90d"
    else:
        date_preset = "last_90d"
    
    # 1. Récupérer les comptes
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
    
    # 2. Récupérer les insights
    all_ads_data = []
    batch_requests = []
    
    for account_id in account_names.keys():
        filtering = '[{"field":"impressions","operator":"GREATER_THAN","value":"0"}]'
        batch_requests.append({
            "method": "GET",
            "relative_url": f"{account_id}/insights?level=ad&date_preset={date_preset}&fields=ad_id,ad_name,campaign_name,adset_name,impressions,spend,clicks,ctr,cpm,reach,frequency,actions,action_values&limit=500&filtering={filtering}"
        })
    
    # Batch API pour les insights
    batch_size = 50
    all_insights_results = []
    
    for i in range(0, len(batch_requests), batch_size):
        batch = batch_requests[i:i+batch_size]
        batch_url = "https://graph.facebook.com/v23.0/"
        batch_params = {
            "access_token": token,
            "batch": json.dumps(batch)
        }
        
        try:
            response = requests.post(batch_url, data=batch_params)
            batch_results = response.json()
            all_insights_results.extend(batch_results)
        except Exception as e:
            print(f"   ❌ Erreur batch insights: {e}")
    
    # Traiter les insights et collecter les ad_ids
    ad_ids_by_account = defaultdict(list)
    insights_by_ad = {}
    
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
    
    total_ads = sum(len(ids) for ids in ad_ids_by_account.values())
    print(f"   {total_ads} annonces trouvées pour {period_days}j")
    
    # 3. Récupérer les formats (creatives)
    creatives_by_ad = {}
    creative_batch_requests = []
    
    for ad_id in insights_by_ad.keys():
        creative_batch_requests.append({
            "method": "GET",
            "relative_url": f"{ad_id}?fields=creative{{video_id,image_url,instagram_permalink_url,object_story_spec}}"
        })
    
    # Exécuter par lots
    for i in range(0, len(creative_batch_requests), batch_size):
        batch = creative_batch_requests[i:i+batch_size]
        batch_url = "https://graph.facebook.com/v23.0/"
        batch_params = {
            "access_token": token,
            "batch": json.dumps(batch)
        }
        
        try:
            response = requests.post(batch_url, data=batch_params)
            batch_results = response.json()
            
            for result in batch_results:
                if result.get("code") == 200:
                    body = json.loads(result["body"])
                    ad_id = body.get("id")
                    if ad_id and "creative" in body:
                        creatives_by_ad[ad_id] = body["creative"]
            
            time.sleep(0.1)  # Éviter rate limiting
            
        except Exception as e:
            print(f"   ❌ Erreur batch creatives: {e}")
    
    # 4. Combiner les données
    format_stats = defaultdict(int)
    
    for ad_id, insights in insights_by_ad.items():
        account_id = None
        account_name = "Unknown"
        for acc_id, ad_list in ad_ids_by_account.items():
            if ad_id in ad_list:
                account_id = acc_id
                account_name = account_names.get(acc_id, "Sans nom")
                break
        
        # Déterminer le format
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
            elif creative.get("object_story_spec"):
                spec = creative["object_story_spec"]
                if spec.get("video_data"):
                    format_type = "VIDEO"
                elif spec.get("link_data", {}).get("child_attachments"):
                    format_type = "CAROUSEL"
        
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
            "account_name": account_name,
            "account_id": account_id,
            "ad_name": insights.get("ad_name", "Sans nom"),
            "ad_id": ad_id,
            "campaign_name": insights.get("campaign_name", ""),
            "adset_name": insights.get("adset_name", ""),
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
    
    return {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "period_days": period_days,
            "date_preset": date_preset,
            "total_ads": len(all_ads_data),
            "total_accounts": len(active_accounts),
            "ads_with_creative": len(creatives_by_ad)
        },
        "format_distribution": dict(format_stats),
        "ads": all_ads_data
    }

def fetch_all_periods():
    """Récupère les données pour les 3 périodes"""
    
    print("🚀 FETCH MULTI-PÉRIODES")
    print("=" * 70)
    print(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    periods = [7, 30, 90]
    results = {}
    
    # Option 1: Séquentiel (plus simple, plus lent)
    for period in periods:
        start_time = time.time()
        data = fetch_period_data(period)
        
        # Sauvegarder
        filename = f"hybrid_data_{period}d.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        elapsed = time.time() - start_time
        print(f"   ✅ {period}j: {data['metadata']['total_ads']} annonces en {elapsed:.1f}s")
        print(f"   💾 Sauvegardé: {filename}")
        
        results[period] = data
    
    # Résumé final
    print("\n" + "=" * 70)
    print("📊 RÉSUMÉ MULTI-PÉRIODES")
    
    for period in periods:
        data = results[period]
        total_ads = data['metadata']['total_ads']
        total_spend = sum(ad['spend'] for ad in data['ads'])
        print(f"\n{period} JOURS:")
        print(f"  • Annonces: {total_ads}")
        print(f"  • Dépenses: ${total_spend:,.0f} MXN")
        
        # Formats
        formats = data['format_distribution']
        if formats:
            print(f"  • Formats:")
            for fmt, count in sorted(formats.items(), key=lambda x: x[1], reverse=True):
                pct = (count/total_ads*100) if total_ads > 0 else 0
                print(f"    - {fmt}: {count} ({pct:.1f}%)")
    
    print("\n✨ Toutes les périodes récupérées avec succès!")
    return results

if __name__ == "__main__":
    print("⚡ Récupération des données pour 7, 30 et 90 jours")
    print("⏱️  Temps estimé: 3-5 minutes")
    print()
    
    start = time.time()
    results = fetch_all_periods()
    elapsed = time.time() - start
    
    print(f"\n⏱️  Temps total: {elapsed/60:.1f} minutes")