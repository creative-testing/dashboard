#!/usr/bin/env python3
"""
Solution HYBRIDE OPTIMISÉE
Combine /insights (pour avoir TOUTES les annonces) avec /ads (pour les formats réels)
"""
import os
import requests
import json
import csv
from dotenv import load_dotenv
from datetime import datetime
from collections import defaultdict
import time

load_dotenv()

def fetch_hybrid_data():
    """Récupère TOUTES les annonces avec formats réels quand disponibles"""
    
    token = os.getenv("FB_TOKEN")
    
    print("🚀 SOLUTION HYBRIDE : INSIGHTS + FORMATS RÉELS")
    print("=" * 70)
    print(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 1. D'abord récupérer les comptes
    accounts_url = "https://graph.facebook.com/v23.0/me/adaccounts"
    params = {
        "access_token": token,
        "fields": "id,name,account_status",
        "limit": 100
    }
    
    print("\n📊 Phase 1: Récupération des comptes...")
    response = requests.get(accounts_url, params=params)
    accounts = response.json().get("data", [])
    active_accounts = [acc for acc in accounts if acc.get("account_status") == 1]
    account_names = {acc["id"]: acc.get("name", "Sans nom") for acc in active_accounts}
    
    print(f"✅ {len(active_accounts)} comptes actifs")
    
    # 2. Récupérer TOUTES les insights (comme dans fast_data)
    print("\n📊 Phase 2: Récupération des INSIGHTS pour toutes les annonces...")
    
    all_ads_data = []
    batch_requests = []
    
    for account_id in account_names.keys():
        filtering = '[{"field":"impressions","operator":"GREATER_THAN","value":"0"}]'
        batch_requests.append({
            "method": "GET",
            "relative_url": f"{account_id}/insights?level=ad&date_preset=last_7d&fields=ad_id,ad_name,campaign_name,adset_name,impressions,spend,clicks,ctr,cpm,reach,frequency,actions,action_values,cost_per_action_type&limit=500&filtering={filtering}"
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
        
        print(f"   Batch insights {i//batch_size + 1}/{(len(batch_requests)-1)//batch_size + 1}...", end="", flush=True)
        
        try:
            response = requests.post(batch_url, data=batch_params)
            batch_results = response.json()
            all_insights_results.extend(batch_results)
            print(" ✅")
        except Exception as e:
            print(f" ❌ {e}")
    
    # Traiter les insights et collecter les ad_ids
    ad_ids_by_account = defaultdict(list)
    insights_by_ad = {}
    
    for idx, result in enumerate(all_insights_results):
        if result.get("code") == 200:
            body = json.loads(result["body"])
            data = body.get("data", [])
            account_id = active_accounts[idx]["id"]
            
            for ad in data:
                ad_id = ad.get("ad_id")
                if ad_id:
                    ad_ids_by_account[account_id].append(ad_id)
                    insights_by_ad[ad_id] = ad
    
    total_ads = sum(len(ids) for ids in ad_ids_by_account.values())
    print(f"✅ {total_ads} annonces avec insights trouvées")
    
    # 3. Récupérer les formats réels pour ces annonces
    print("\n📊 Phase 3: Récupération des FORMATS RÉELS (creative data)...")
    
    creatives_by_ad = {}
    creative_batch_requests = []
    
    # Créer les requêtes batch pour récupérer les creatives
    for ad_id in insights_by_ad.keys():
        creative_batch_requests.append({
            "method": "GET",
            "relative_url": f"{ad_id}?fields=creative{{video_id,image_url,instagram_permalink_url,object_story_spec}}"
        })
    
    print(f"   Préparation de {len(creative_batch_requests)} requêtes pour les creatives...")
    
    # Exécuter par lots de 50
    for i in range(0, len(creative_batch_requests), batch_size):
        batch = creative_batch_requests[i:i+batch_size]
        batch_url = "https://graph.facebook.com/v23.0/"
        batch_params = {
            "access_token": token,
            "batch": json.dumps(batch)
        }
        
        print(f"   Batch creatives {i//batch_size + 1}/{(len(creative_batch_requests)-1)//batch_size + 1}...", end="", flush=True)
        
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
            time.sleep(0.2)  # Petite pause pour éviter rate limiting
            
        except Exception as e:
            print(f" ❌ {e}")
    
    print(f"✅ {len(creatives_by_ad)} creatives récupérés sur {total_ads} annonces")
    
    # 4. Combiner insights et formats
    print("\n📊 Phase 4: Fusion des données...")
    
    format_stats = defaultdict(int)
    
    for ad_id, insights in insights_by_ad.items():
        # Récupérer l'account_id
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
            
            # Détection du format réel
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
        else:
            # Fallback: deviner depuis le nom
            ad_name = insights.get("ad_name", "").lower()
            if "video" in ad_name or "vid" in ad_name:
                format_type = "VIDEO*"  # * indique que c'est deviné
            elif "carousel" in ad_name or "carrusel" in ad_name:
                format_type = "CAROUSEL*"
            elif "image" in ad_name or "imagen" in ad_name:
                format_type = "IMAGE*"
        
        format_stats[format_type] += 1
        
        # Extraire les métriques
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
        
        # ROAS
        roas = (purchase_value / spend) if spend > 0 else 0
        
        ad_data = {
            "account_name": account_name,
            "account_id": account_id,
            "ad_name": insights.get("ad_name", "Sans nom"),
            "ad_id": ad_id,
            "campaign_name": insights.get("campaign_name", ""),
            "adset_name": insights.get("adset_name", ""),
            "format": format_type,
            "format_source": "api" if ad_id in creatives_by_ad else "guessed",
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
    
    # 5. Sauvegarder les résultats
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # CSV
    csv_filename = f"hybrid_data_{timestamp}.csv"
    if all_ads_data:
        with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = list(all_ads_data[0].keys())
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_ads_data)
    
    # JSON
    json_filename = f"hybrid_data_{timestamp}.json"
    output_data = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "total_ads": len(all_ads_data),
            "total_accounts": len(active_accounts),
            "ads_with_creative": len(creatives_by_ad),
            "date_range": "last_7_days"
        },
        "format_distribution": dict(format_stats),
        "ads": all_ads_data
    }
    
    with open(json_filename, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    # 6. Afficher le résumé
    print(f"\n" + "=" * 70)
    print(f"📊 RÉSUMÉ HYBRIDE")
    print(f"✅ {len(all_ads_data)} annonces totales (comme insights)")
    print(f"✅ {len(creatives_by_ad)} avec formats réels depuis l'API")
    print(f"✅ {len(all_ads_data) - len(creatives_by_ad)} avec formats devinés ou unknown")
    print(f"💾 Fichiers: {csv_filename} et {json_filename}")
    
    if format_stats:
        print(f"\n📈 DISTRIBUTION DES FORMATS:")
        total = sum(format_stats.values())
        
        # Séparer formats réels et devinés
        real_formats = {k: v for k, v in format_stats.items() if not k.endswith('*')}
        guessed_formats = {k: v for k, v in format_stats.items() if k.endswith('*')}
        
        print("  Formats RÉELS (depuis API):")
        for fmt, count in sorted(real_formats.items(), key=lambda x: x[1], reverse=True):
            pct = (count/total*100) if total > 0 else 0
            print(f"    {fmt:12} : {count:5} ({pct:.1f}%)")
        
        if guessed_formats:
            print("  Formats DEVINÉS (depuis noms):")
            for fmt, count in sorted(guessed_formats.items(), key=lambda x: x[1], reverse=True):
                pct = (count/total*100) if total > 0 else 0
                print(f"    {fmt:12} : {count:5} ({pct:.1f}%)")
    
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
    print("⚡ SOLUTION HYBRIDE OPTIMISÉE")
    print("Combine le meilleur des deux mondes :")
    print("  • TOUTES les annonces (comme insights)")
    print("  • Formats RÉELS quand disponibles (comme ads)")
    print()
    
    filename = fetch_hybrid_data()
    if filename:
        print(f"\n✨ Succès! Données dans {filename}")