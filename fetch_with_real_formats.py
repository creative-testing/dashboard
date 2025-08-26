#!/usr/bin/env python3
"""
Récupère les données avec les VRAIS formats depuis l'API Meta
En utilisant la méthode du projet agente_creativo_ia
"""
import os
import requests
import json
import csv
from dotenv import load_dotenv
from datetime import datetime
from collections import defaultdict

load_dotenv()

def fetch_data_with_real_formats():
    """Récupère les données avec les vrais formats depuis les champs creative"""
    
    token = os.getenv("FB_TOKEN")
    
    print("🚀 RÉCUPÉRATION AVEC FORMATS RÉELS DEPUIS L'API")
    print("=" * 70)
    print(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Récupérer les comptes
    accounts_url = "https://graph.facebook.com/v23.0/me/adaccounts"
    params = {
        "access_token": token,
        "fields": "id,name,account_status",
        "limit": 100
    }
    
    print("📊 Récupération des comptes...")
    response = requests.get(accounts_url, params=params)
    accounts = response.json().get("data", [])
    active_accounts = [acc for acc in accounts if acc.get("account_status") == 1]
    
    print(f"✅ {len(active_accounts)} comptes actifs")
    
    all_ads_data = []
    format_stats = defaultdict(int)
    
    # Utiliser Batch API pour la rapidité
    print("\n📦 Récupération par batch...")
    
    batch_requests = []
    account_names = {}
    
    for account in active_accounts:
        account_id = account["id"]
        account_names[account_id] = account.get("name", "Sans nom")
        
        # IMPORTANT: On demande creative{video_id,image_url} pour chaque ad
        batch_requests.append({
            "method": "GET",
            "relative_url": f"{account_id}/ads?fields=id,name,creative{{video_id,image_url}},insights.date_preset(last_7d){{impressions,spend,clicks,ctr,cpm,reach,frequency,actions,action_values,cost_per_action_type}}&limit=500"
        })
    
    # Traiter par lots de 50
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
            print(f" ❌ {e}")
    
    # Traiter les résultats
    print("\n📊 Traitement et détection des formats...")
    
    for idx, result in enumerate(all_results):
        if result.get("code") == 200:
            body = json.loads(result["body"])
            ads = body.get("data", [])
            account_id = active_accounts[idx]["id"]
            account_name = account_names[account_id]
            
            for ad in ads:
                # Récupérer les insights
                insights = {}
                if ad.get("insights") and ad["insights"].get("data"):
                    insights = ad["insights"]["data"][0]
                
                impressions = int(insights.get("impressions", 0))
                if impressions == 0:
                    continue
                
                spend = float(insights.get("spend", 0))
                
                # DÉTERMINER LE FORMAT RÉEL
                format_type = "UNKNOWN"
                creative = ad.get("creative", {})
                media_url = ""
                
                if creative.get("video_id"):
                    format_type = "VIDEO"
                    media_url = f"https://www.facebook.com/watch/?v={creative['video_id']}"
                elif creative.get("image_url"):
                    format_type = "IMAGE"
                    media_url = creative["image_url"]
                
                # Métriques
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
                
                # ROAS
                roas = (purchase_value / spend) if spend > 0 else 0
                
                ad_data = {
                    "account_name": account_name,
                    "account_id": account_id,
                    "ad_name": ad.get("name", "Sans nom"),
                    "ad_id": ad.get("id", ""),
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
                format_stats[format_type] += 1
    
    # Sauvegarder
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # CSV
    csv_filename = f"real_formats_data_{timestamp}.csv"
    if all_ads_data:
        with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = list(all_ads_data[0].keys())
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_ads_data)
    
    # JSON
    json_filename = f"real_formats_data_{timestamp}.json"
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
    print(f"📊 RÉSUMÉ AVEC FORMATS RÉELS")
    print(f"✅ {len(all_ads_data)} annonces actives")
    print(f"💾 Fichiers: {csv_filename} et {json_filename}")
    
    if format_stats:
        print(f"\n📈 DISTRIBUTION DES FORMATS (RÉELS depuis l'API):")
        total = sum(format_stats.values())
        for fmt, count in sorted(format_stats.items(), key=lambda x: x[1], reverse=True):
            pct = (count/total*100) if total > 0 else 0
            print(f"  {fmt:12} : {count:5} ({pct:.1f}%)")
    
    # Top comptes
    if all_ads_data:
        account_spend = defaultdict(float)
        for ad in all_ads_data:
            account_spend[ad["account_name"]] += ad["spend"]
        
        print(f"\n💰 TOP 5 COMPTES (MXN):")
        for acc, spend in sorted(account_spend.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"  {acc[:30]:30} : ${spend:,.0f}")
    
    return json_filename

if __name__ == "__main__":
    print("⚡ Récupération avec VRAIS formats depuis l'API")
    filename = fetch_data_with_real_formats()
    if filename:
        print(f"\n✨ Succès! Données dans {filename}")