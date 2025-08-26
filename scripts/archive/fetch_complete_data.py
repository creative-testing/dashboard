#!/usr/bin/env python3
"""
Récupère les données COMPLÈTES depuis l'API Meta avec les vrais formats
Remplace all_ad_names_export.py avec détection correcte des formats
"""
import os
import requests
import csv
import json
from dotenv import load_dotenv
from datetime import datetime
from collections import defaultdict
import time

load_dotenv()

def detect_real_format(ad_data):
    """Détermine le vrai format depuis les données de l'API"""
    
    creative = ad_data.get("creative", {})
    
    # 1. Vérifier object_story_spec (le plus fiable)
    object_story_spec = creative.get("object_story_spec", {})
    if object_story_spec:
        # VIDEO
        if object_story_spec.get("video_data"):
            return "VIDEO"
        
        # CAROUSEL
        link_data = object_story_spec.get("link_data", {})
        if link_data.get("child_attachments"):
            return "CAROUSEL"
        
        # IMAGE via link_data
        if link_data.get("image_hash") or link_data.get("picture"):
            return "IMAGE"
    
    # 2. Vérifier les champs directs du creative
    if creative.get("video_id"):
        return "VIDEO"
    
    if creative.get("image_url") or creative.get("image_hash"):
        return "IMAGE"
    
    # 3. Si Instagram post, difficile à déterminer sans plus d'info
    if creative.get("instagram_permalink_url"):
        return "INSTAGRAM_POST"
    
    return "UNKNOWN"

def fetch_complete_data():
    """Récupère toutes les données avec formats réels depuis l'API"""
    
    token = os.getenv("FB_TOKEN")
    
    print("🚀 RÉCUPÉRATION DES DONNÉES COMPLÈTES AVEC FORMATS RÉELS")
    print("=" * 70)
    print(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Récupérer tous les comptes
    accounts_url = "https://graph.facebook.com/v23.0/me/adaccounts"
    params = {
        "access_token": token,
        "fields": "id,name,account_status",
        "limit": 100
    }
    
    response = requests.get(accounts_url, params=params)
    accounts_data = response.json()
    
    if "error" in accounts_data:
        print(f"❌ Erreur: {accounts_data['error']['message']}")
        return
    
    accounts = accounts_data.get("data", [])
    active_accounts = [acc for acc in accounts if acc.get("account_status") == 1]
    
    print(f"✅ {len(active_accounts)} comptes actifs trouvés\n")
    
    # Structures pour stocker les données
    all_ads_data = []
    format_stats = defaultdict(int)
    account_stats = defaultdict(lambda: {"ads": 0, "spend": 0, "impressions": 0})
    
    # Pour chaque compte actif
    for i, account in enumerate(active_accounts, 1):
        account_id = account["id"]
        account_name = account.get("name", "Sans nom")
        
        print(f"[{i}/{len(active_accounts)}] {account_name}...", end="", flush=True)
        
        # Récupérer les insights ET les créatifs
        ads_url = f"https://graph.facebook.com/v23.0/{account_id}/ads"
        ads_params = {
            "access_token": token,
            "fields": "id,name,creative{object_story_spec,video_id,image_url,image_hash,instagram_permalink_url,title,body},insights{impressions,spend,clicks,ctr,cpm,reach,frequency,actions,action_values}",
            "time_range": "{'since':'2025-08-19','until':'2025-08-25'}",  # 7 derniers jours
            "limit": 250
        }
        
        try:
            has_more = True
            account_ads = 0
            next_url = None
            
            while has_more:
                if next_url:
                    ads_response = requests.get(next_url)
                else:
                    ads_response = requests.get(ads_url, params=ads_params)
                
                ads_data = ads_response.json()
                
                if "data" in ads_data:
                    ads = ads_data.get("data", [])
                    
                    for ad in ads:
                        # Récupérer les insights
                        insights = ad.get("insights", {}).get("data", [{}])[0] if ad.get("insights") else {}
                        
                        spend = float(insights.get("spend", 0))
                        impressions = int(insights.get("impressions", 0))
                        
                        # Skip ads with no activity
                        if impressions == 0:
                            continue
                        
                        # Déterminer le format réel
                        format_type = detect_real_format(ad)
                        
                        # Calculer les métriques
                        clicks = int(insights.get("clicks", 0))
                        ctr = float(insights.get("ctr", 0))
                        cpm = float(insights.get("cpm", 0))
                        reach = int(insights.get("reach", 0))
                        frequency = float(insights.get("frequency", 0))
                        
                        # Extraire les conversions
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
                        
                        # Calculer ROAS
                        roas = (purchase_value / spend) if spend > 0 else 0
                        
                        # Obtenir l'URL du créatif
                        creative = ad.get("creative", {})
                        media_url = ""
                        if creative.get("instagram_permalink_url"):
                            media_url = creative["instagram_permalink_url"]
                        elif creative.get("video_id"):
                            media_url = f"https://www.facebook.com/watch/?v={creative['video_id']}"
                        elif creative.get("image_url"):
                            media_url = creative["image_url"]
                        
                        # Ajouter aux données
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
                            "media_url": media_url,
                            "title": creative.get("title", ""),
                            "body": creative.get("body", "")[:200] if creative.get("body") else ""
                        }
                        
                        all_ads_data.append(ad_data)
                        format_stats[format_type] += 1
                        account_stats[account_name]["ads"] += 1
                        account_stats[account_name]["spend"] += spend
                        account_stats[account_name]["impressions"] += impressions
                        account_ads += 1
                    
                    # Pagination
                    if "paging" in ads_data and "next" in ads_data["paging"]:
                        next_url = ads_data["paging"]["next"]
                    else:
                        has_more = False
                else:
                    has_more = False
            
            print(f" ✅ {account_ads} annonces actives")
            
            # Petite pause pour éviter rate limiting
            if i < len(active_accounts):
                time.sleep(0.5)
                
        except Exception as e:
            print(f" ❌ Erreur: {e}")
    
    # Sauvegarder les données
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # 1. CSV complet
    csv_filename = f"complete_data_{timestamp}.csv"
    with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = list(all_ads_data[0].keys()) if all_ads_data else []
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_ads_data)
    
    # 2. JSON avec statistiques
    json_filename = f"complete_data_{timestamp}.json"
    output_data = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "total_ads": len(all_ads_data),
            "total_accounts": len(active_accounts),
            "date_range": "last_7_days"
        },
        "format_distribution": dict(format_stats),
        "account_stats": dict(account_stats),
        "ads": all_ads_data
    }
    
    with open(json_filename, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    # Afficher le résumé
    print(f"\n" + "=" * 70)
    print(f"📊 RÉSUMÉ DE LA RÉCUPÉRATION")
    print(f"-" * 40)
    print(f"✅ Total: {len(all_ads_data)} annonces actives")
    print(f"💾 Fichiers sauvegardés:")
    print(f"   • CSV: {csv_filename}")
    print(f"   • JSON: {json_filename}")
    
    print(f"\n📈 DISTRIBUTION DES FORMATS RÉELS:")
    print(f"-" * 40)
    total = sum(format_stats.values())
    for format_type, count in sorted(format_stats.items(), key=lambda x: x[1], reverse=True):
        percentage = (count / total * 100) if total > 0 else 0
        print(f"  {format_type:15} : {count:5} annonces ({percentage:.1f}%)")
    
    print(f"\n🏆 TOP 5 COMPTES PAR DÉPENSES:")
    print(f"-" * 40)
    top_accounts = sorted(account_stats.items(), key=lambda x: x[1]["spend"], reverse=True)[:5]
    for account_name, stats in top_accounts:
        print(f"  {account_name[:30]:30} : ${stats['spend']:.2f} MXN ({stats['ads']} ads)")
    
    print(f"\n✨ Données mises à jour avec succès!")
    
    return json_filename

if __name__ == "__main__":
    filename = fetch_complete_data()
    if filename:
        print(f"\n🎯 Prochaine étape: Analyser {filename} pour créer le dashboard")