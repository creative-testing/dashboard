#!/usr/bin/env python3
"""
Exporte TOUS les noms d'annonces dans un fichier CSV pour analyse
"""
import os
import requests
import csv
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

def export_all_ad_names():
    """Exporte tous les noms d'annonces dans un CSV"""
    
    token = os.getenv("FB_TOKEN")
    
    print("📊 EXPORT DE TOUS LES NOMS D'ANNONCES")
    print("=" * 70)
    
    # Récupérer tous les comptes
    accounts_url = f"https://graph.facebook.com/v23.0/me/adaccounts"
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
    
    # Préparer le CSV
    csv_filename = f"ad_names_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['account_name', 'account_id', 'ad_name', 'ad_id', 'impressions', 'spend']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        total_ads = 0
        
        # Pour chaque compte actif
        for i, account in enumerate(active_accounts, 1):
            account_id = account["id"]
            account_name = account.get("name", "Sans nom")
            
            print(f"Traitement {i}/{len(active_accounts)}: {account_name}...", end="")
            
            # Récupérer TOUTES les annonces du compte
            insights_url = f"https://graph.facebook.com/v23.0/{account_id}/insights"
            insights_params = {
                "access_token": token,
                "level": "ad",
                "date_preset": "last_7d",
                "fields": "ad_name,ad_id,impressions,spend",
                "limit": 1000,  # Maximum pour récupérer toutes les annonces
                "filtering": "[{'field':'impressions','operator':'GREATER_THAN','value':'0'}]"
            }
            
            try:
                # Gérer la pagination pour récupérer TOUTES les annonces
                has_more = True
                account_ads = 0
                next_url = None
                
                while has_more:
                    if next_url:
                        insights_response = requests.get(next_url)
                    else:
                        insights_response = requests.get(insights_url, params=insights_params)
                    
                    insights_data = insights_response.json()
                    
                    if "data" in insights_data:
                        ads = insights_data["data"]
                        
                        for ad in ads:
                            writer.writerow({
                                'account_name': account_name,
                                'account_id': account_id,
                                'ad_name': ad.get("ad_name", "Sans nom"),
                                'ad_id': ad.get("ad_id", ""),
                                'impressions': ad.get("impressions", "0"),
                                'spend': ad.get("spend", "0")
                            })
                            account_ads += 1
                            total_ads += 1
                        
                        # Vérifier s'il y a d'autres pages
                        if "paging" in insights_data and "next" in insights_data["paging"]:
                            next_url = insights_data["paging"]["next"]
                        else:
                            has_more = False
                    else:
                        has_more = False
                
                print(f" ✅ {account_ads} annonces")
                
            except Exception as e:
                print(f" ❌ Erreur: {e}")
    
    print(f"\n" + "=" * 70)
    print(f"📁 EXPORT TERMINÉ !")
    print(f"   • Total: {total_ads} annonces")
    print(f"   • Fichier: {csv_filename}")
    print(f"\n💡 Tu peux maintenant analyser ce fichier pour trouver des patterns !")
    
    # Afficher aussi un aperçu des patterns
    print(f"\n🔍 APERÇU RAPIDE DES PATTERNS:")
    
    # Relire le CSV pour analyse rapide
    with open(csv_filename, 'r', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        ad_names = [row['ad_name'] for row in reader]
    
    # Patterns basiques
    with_pipe = sum(1 for name in ad_names if '|' in name)
    with_slash = sum(1 for name in ad_names if '/' in name)
    with_dash = sum(1 for name in ad_names if '-' in name)
    with_underscore = sum(1 for name in ad_names if '_' in name)
    with_hook = sum(1 for name in ad_names if 'hook' in name.lower())
    with_video = sum(1 for name in ad_names if 'video' in name.lower() or 'vid' in name.lower())
    with_image = sum(1 for name in ad_names if 'image' in name.lower() or 'img' in name.lower() or 'imagen' in name.lower())
    
    print(f"   • Avec pipe '|': {with_pipe}")
    print(f"   • Avec slash '/': {with_slash}")
    print(f"   • Avec tiret '-': {with_dash}")
    print(f"   • Avec underscore '_': {with_underscore}")
    print(f"   • Contient 'hook': {with_hook}")
    print(f"   • Contient 'video/vid': {with_video}")
    print(f"   • Contient 'image/img': {with_image}")

if __name__ == "__main__":
    export_all_ad_names()