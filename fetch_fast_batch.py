#!/usr/bin/env python3
"""
Version RAPIDE - Récupère toutes les données en une seule requête via Insights API
au niveau Business Manager au lieu de parcourir compte par compte
"""
import os
import requests
import json
from dotenv import load_dotenv
from datetime import datetime
from collections import defaultdict
import time

load_dotenv()

def detect_format_from_name(ad_name):
    """Détection basique depuis le nom en attendant mieux"""
    name_lower = ad_name.lower()
    if 'video' in name_lower or 'vid' in name_lower:
        return "VIDEO"
    elif 'carousel' in name_lower or 'carrusel' in name_lower:
        return "CAROUSEL"
    elif 'reel' in name_lower:
        return "VIDEO"
    elif 'imagen' in name_lower or 'image' in name_lower:
        return "IMAGE"
    return "UNKNOWN"

def fetch_all_insights_batch():
    """Récupère TOUTES les insights en une seule grosse requête"""
    
    token = os.getenv("FB_TOKEN")
    
    print("🚀 RÉCUPÉRATION RAPIDE PAR BATCH")
    print("=" * 70)
    print(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # D'abord, récupérer tous les account IDs d'un coup
    accounts_url = "https://graph.facebook.com/v23.0/me/adaccounts"
    params = {
        "access_token": token,
        "fields": "id,name,account_status",
        "limit": 100
    }
    
    print("📊 Récupération des comptes...")
    response = requests.get(accounts_url, params=params)
    accounts_data = response.json()
    
    accounts = accounts_data.get("data", [])
    active_accounts = [acc for acc in accounts if acc.get("account_status") == 1]
    account_ids = [acc["id"] for acc in active_accounts]
    
    print(f"✅ {len(active_accounts)} comptes actifs")
    
    # Créer un mapping account_id -> account_name
    account_names = {acc["id"]: acc.get("name", "Sans nom") for acc in active_accounts}
    
    all_ads_data = []
    format_stats = defaultdict(int)
    
    # MÉTHODE 1: Requête Batch officielle Facebook
    print("\n📦 Utilisation de l'API Batch pour tout récupérer d'un coup...")
    
    batch_requests = []
    for account_id in account_ids:
        filtering = '[{"field":"impressions","operator":"GREATER_THAN","value":"0"}]'
        batch_requests.append({
            "method": "GET",
            "relative_url": f"{account_id}/insights?level=ad&date_preset=last_7d&fields=ad_id,ad_name,campaign_name,adset_name,impressions,spend,clicks,ctr,cpm,reach,frequency,actions,action_values,cost_per_action_type&limit=500&filtering={filtering}"
        })
    
    # Diviser en lots de 50 (limite de l'API Batch)
    batch_size = 50
    all_results = []
    
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
            all_results.extend(batch_results)
            print(" ✅")
        except Exception as e:
            print(f" ❌ Erreur: {e}")
    
    # Traiter les résultats
    print("\n📊 Traitement des données...")
    
    for idx, result in enumerate(all_results):
        if result.get("code") == 200:
            body = json.loads(result["body"])
            data = body.get("data", [])
            account_id = account_ids[idx]
            account_name = account_names[account_id]
            
            for ad in data:
                spend = float(ad.get("spend", 0))
                impressions = int(ad.get("impressions", 0))
                
                if impressions == 0:
                    continue
                
                # Extraire les métriques
                clicks = int(ad.get("clicks", 0))
                ctr = float(ad.get("ctr", 0))
                cpm = float(ad.get("cpm", 0))
                reach = int(ad.get("reach", 0))
                frequency = float(ad.get("frequency", 0))
                
                # Conversions
                purchases = 0
                purchase_value = 0
                actions = ad.get("actions", [])
                action_values = ad.get("action_values", [])
                
                for action in actions:
                    if action.get("action_type") in ["purchase", "omni_purchase"]:
                        purchases = int(action.get("value", 0))
                        break
                
                for action_value in action_values:
                    if action_value.get("action_type") in ["purchase", "omni_purchase"]:
                        purchase_value = float(action_value.get("value", 0))
                        break
                
                # ROAS
                roas = (purchase_value / spend) if spend > 0 else 0
                
                # Format (temporaire depuis le nom)
                format_type = detect_format_from_name(ad.get("ad_name", ""))
                
                ad_data = {
                    "account_name": account_name,
                    "account_id": account_id,
                    "ad_name": ad.get("ad_name", "Sans nom"),
                    "ad_id": ad.get("ad_id", ""),
                    "campaign_name": ad.get("campaign_name", ""),
                    "adset_name": ad.get("adset_name", ""),
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
                    "roas": roas
                }
                
                all_ads_data.append(ad_data)
                format_stats[format_type] += 1
    
    # Sauvegarder
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # CSV
    csv_filename = f"fast_data_{timestamp}.csv"
    if all_ads_data:
        import csv
        with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = list(all_ads_data[0].keys())
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_ads_data)
    
    # JSON
    json_filename = f"fast_data_{timestamp}.json"
    output_data = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "total_ads": len(all_ads_data),
            "total_accounts": len(active_accounts),
            "date_range": "last_7_days"
        },
        "format_distribution": dict(format_stats),
        "ads": all_ads_data
    }
    
    with open(json_filename, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    # Résumé
    print(f"\n" + "=" * 70)
    print(f"📊 RÉSUMÉ")
    print(f"✅ {len(all_ads_data)} annonces actives récupérées")
    print(f"💾 Fichiers: {csv_filename} et {json_filename}")
    
    if format_stats:
        print(f"\n📈 FORMATS (basé sur les noms):")
        total = sum(format_stats.values())
        for fmt, count in sorted(format_stats.items(), key=lambda x: x[1], reverse=True):
            pct = (count/total*100) if total > 0 else 0
            print(f"  {fmt:12} : {count:5} ({pct:.1f}%)")
    
    # Top spenders
    if all_ads_data:
        account_spend = defaultdict(float)
        for ad in all_ads_data:
            account_spend[ad["account_name"]] += ad["spend"]
        
        print(f"\n💰 TOP 5 COMPTES:")
        for acc, spend in sorted(account_spend.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"  {acc[:30]:30} : ${spend:,.0f} MXN")
    
    return json_filename

if __name__ == "__main__":
    print("⚡ Version RAPIDE avec Batch API")
    filename = fetch_all_insights_batch()
    if filename:
        print(f"\n✨ Terminé! Données dans {filename}")