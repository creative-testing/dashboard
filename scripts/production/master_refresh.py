#!/usr/bin/env python3
"""
SCRIPT MASTER INTELLIGENT
Refresh toutes les périodes avec date de référence dynamique (toujours hier)
Solution définitive pour cohérence des données
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
    """Date de référence intelligente : toujours hier (journée complète)"""
    yesterday = datetime.now() - timedelta(days=1)
    return yesterday.strftime('%Y-%m-%d')

def calculate_period_dates(period_days, reference_date):
    """Calcule fenêtre pour une période depuis date référence"""
    ref = datetime.strptime(reference_date, '%Y-%m-%d')
    end_date = ref
    start_date = ref - timedelta(days=period_days - 1)
    
    return start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')

def fetch_account_insights_optimized(account, token, since_date, until_date):
    """Fetch optimisé pour un compte"""
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
        
        # Pagination complète
        all_ads = []
        current_url = url
        page = 0
        
        while current_url and page < 30:  # Limite sécurité
            if page == 0:
                response = requests.get(current_url, params=params)
            else:
                response = requests.get(current_url)
            
            data = response.json()
            
            if "data" in data:
                ads = data["data"]
                
                # Enrichir avec account info
                for ad in ads:
                    ad['account_name'] = account_name
                    ad['account_id'] = account_id
                
                all_ads.extend(ads)
                
                # Pagination
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

def fetch_creatives_parallel(ad_ids, token):
    """Fetch creatives en parallèle"""
    
    def fetch_batch(ad_ids_batch):
        batch_requests = [
            {"method": "GET", "relative_url": f"{ad_id}?fields=creative{{video_id,image_url,instagram_permalink_url}}"}
            for ad_id in ad_ids_batch
        ]
        
        try:
            response = requests.post("https://graph.facebook.com/v23.0/", data={
                "access_token": token,
                "batch": json.dumps(batch_requests)
            })
            
            results = response.json()
            creatives = {}
            
            # ✅ Fix: Vérifier que results est une liste
            if not isinstance(results, list):
                print(f"⚠️  Batch response not a list: {type(results)}")
                return {}
            
            for result in results:
                # ✅ Fix: Vérifier que result est un dict  
                if not isinstance(result, dict):
                    continue
                    
                if result.get("code") == 200:
                    body = json.loads(result["body"])
                    ad_id = body.get("id")
                    if ad_id and "creative" in body:
                        creatives[ad_id] = body["creative"]
            
            return creatives
            
        except:
            return {}
    
    # Diviser en batches
    batch_size = 100
    batches = [ad_ids[i:i+batch_size] for i in range(0, len(ad_ids), batch_size)]
    
    all_creatives = {}
    
    with ThreadPoolExecutor(max_workers=30) as executor:  # Agressif pour M1 Pro
        futures = [executor.submit(fetch_batch, batch) for batch in batches]
        
        for future in as_completed(futures):
            batch_creatives = future.result()
            all_creatives.update(batch_creatives)
    
    return all_creatives

def master_refresh():
    """Fonction master : refresh tout avec cohérence"""
    
    token = os.getenv("FB_TOKEN")
    reference_date = get_reference_date()
    
    print("🚀 MASTER REFRESH - SOLUTION INTELLIGENTE")
    print("=" * 70)
    print(f"📅 Date référence (hier): {reference_date}")
    print(f"🕐 Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"💻 Optimisé pour MacBook M1 Pro")
    
    start_master = time.time()
    
    # 1. Comptes (une seule fois)
    print(f"\n📊 Récupération comptes...")
    accounts_response = requests.get("https://graph.facebook.com/v23.0/me/adaccounts", params={
        "access_token": token,
        "fields": "id,name,account_status",
        "limit": 100
    })
    
    accounts = accounts_response.json().get("data", [])
    active_accounts = [acc for acc in accounts if acc.get("account_status") == 1]
    
    print(f"✅ {len(active_accounts)} comptes actifs")
    
    # 2. Refresh chaque période
    results_summary = {}
    
    for period in [3, 7, 14, 30, 90]:  # Pablo's request
        since_date, until_date = calculate_period_dates(period, reference_date)
        
        print(f"\n🔄 PÉRIODE {period}J ({since_date} → {until_date})")
        print("-" * 50)
        
        period_start = time.time()
        
        # Insights parallèles
        print(f"   📊 Insights parallèles...")
        all_insights = []
        
        with ThreadPoolExecutor(max_workers=25) as executor:  # M1 Pro optimized
            futures = [
                executor.submit(fetch_account_insights_optimized, acc, token, since_date, until_date)
                for acc in active_accounts
            ]
            
            for future in as_completed(futures):
                account_insights = future.result()
                all_insights.extend(account_insights)
        
        print(f"   ✅ {len(all_insights)} insights")
        
        # Creatives parallèles
        print(f"   🎨 Creatives parallèles...")
        ad_ids = [ad.get("ad_id") for ad in all_insights if ad.get("ad_id")]
        creatives_by_ad = fetch_creatives_parallel(ad_ids, token)
        
        print(f"   ✅ {len(creatives_by_ad)} creatives")
        
        # Processing
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
            
            # Métriques complètes
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
        
        # Sauvegarder avec métadonnées intelligentes
        output = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "reference_date": reference_date,
                "period_days": period,
                "date_range": f"{since_date} to {until_date}",
                "method": "master_coherent_refresh",
                "total_ads": len(processed_ads),
                "ads_with_creative": len(creatives_by_ad)
            },
            "format_distribution": dict(format_stats),
            "ads": processed_ads
        }
        
        filename = f"data/current/hybrid_data_{period}d.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        period_time = time.time() - period_start
        total_spend = sum(ad['spend'] for ad in processed_ads)
        
        print(f"   ✅ {period}j: {len(processed_ads)} ads, ${total_spend:,.0f} MXN en {period_time:.1f}s")
        
        results_summary[period] = {
            'ads': len(processed_ads),
            'spend': total_spend,
            'time': period_time
        }
    
    # Résumé final
    master_time = time.time() - start_master
    
    print(f"\n" + "=" * 70)
    print(f"🎉 MASTER REFRESH TERMINÉ")
    print(f"⚡ Temps total: {master_time/60:.1f} minutes")
    print(f"📅 Toutes périodes cohérentes depuis: {reference_date}")
    
    print(f"\n📊 RÉSUMÉ PAR PÉRIODE:")
    for period, stats in results_summary.items():
        print(f"  {period:2}j: {stats['ads']:4} ads, ${stats['spend']:>8,.0f} MXN, {stats['time']:4.1f}s")
    
    # Créer fichier de config pour l'interface
    config_output = {
        "last_update": datetime.now().isoformat(),
        "reference_date": reference_date,
        "periods_available": list(results_summary.keys()),
        "total_execution_time": master_time
    }
    
    with open('data/current/refresh_config.json', 'w') as f:
        json.dump(config_output, f, indent=2)
    
    print(f"\n💾 Config sauvegardée pour interface")
    return results_summary

if __name__ == "__main__":
    print("🤖 SCRIPT MASTER - REFRESH INTELLIGENT")
    print("🎯 Toutes périodes cohérentes depuis date référence dynamique")
    print("⚡ Optimisé MacBook M1 Pro - Parallélisation aggressive") 
    print()
    
    results = master_refresh()
    
    if results:
        print(f"\n✅ SUCCESS! Toutes données cohérentes et prêtes")
        print(f"🎯 Interface peut maintenant afficher dates précises")
        print(f"🚀 Dashboard Pablo ready!")