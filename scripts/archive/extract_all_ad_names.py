#!/usr/bin/env python3
"""
Extrait TOUS les noms d'annonces des 7 derniers jours
depuis TOUS les comptes pour analyser les nomenclatures
"""
import os
import requests
from dotenv import load_dotenv
from collections import defaultdict

load_dotenv()

def extract_all_ad_names():
    """Récupère tous les noms d'annonces de tous les comptes"""
    
    token = os.getenv("FB_TOKEN")
    
    print("🔍 EXTRACTION DE TOUS LES NOMS D'ANNONCES (7 derniers jours)")
    print("=" * 70)
    
    # 1. Récupérer tous les comptes
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
    
    print(f"📊 {len(active_accounts)} comptes actifs sur {len(accounts)} total\n")
    
    all_ad_names = []
    accounts_with_ads = []
    
    # 2. Pour chaque compte actif, récupérer les noms d'annonces
    for i, account in enumerate(active_accounts, 1):
        account_id = account["id"]
        account_name = account.get("name", "Sans nom")
        
        # Récupérer les insights
        insights_url = f"https://graph.facebook.com/v23.0/{account_id}/insights"
        insights_params = {
            "access_token": token,
            "level": "ad",
            "date_preset": "last_7d",
            "fields": "ad_name,impressions",
            "limit": 500,  # Récupérer plus d'annonces
            "filtering": "[{'field':'impressions','operator':'GREATER_THAN','value':'0'}]"
        }
        
        try:
            insights_response = requests.get(insights_url, params=insights_params)
            insights_data = insights_response.json()
            
            if "data" in insights_data:
                ads = insights_data["data"]
                if ads:
                    print(f"{i}. {account_name}: {len(ads)} annonces")
                    accounts_with_ads.append(account_name)
                    
                    for ad in ads:
                        ad_name = ad.get("ad_name", "Sans nom")
                        all_ad_names.append({
                            "account": account_name,
                            "name": ad_name
                        })
                    
                    # Afficher quelques exemples
                    if len(ads) > 0:
                        print(f"   Exemples:")
                        for j, ad in enumerate(ads[:3], 1):
                            print(f"   • {ad.get('ad_name', 'Sans nom')}")
                        if len(ads) > 3:
                            print(f"   ... et {len(ads) - 3} autres")
                    print()
        
        except Exception as e:
            pass  # Ignorer les erreurs silencieusement
    
    # 3. Analyser les patterns de nomenclature
    print("\n" + "=" * 70)
    print("📝 ANALYSE DES NOMENCLATURES\n")
    
    print(f"✅ Total: {len(all_ad_names)} annonces depuis {len(accounts_with_ads)} comptes\n")
    
    # Détecter les patterns
    patterns = defaultdict(list)
    
    for ad in all_ad_names:
        name = ad["name"]
        
        # Pattern avec pipe |
        if "|" in name:
            patterns["pipe_separator"].append(name)
        
        # Pattern avec underscore _
        if "_" in name and "|" not in name:
            patterns["underscore_separator"].append(name)
        
        # Pattern avec parenthèses
        if "(" in name and ")" in name:
            patterns["with_parentheses"].append(name)
        
        # Pattern avec dates (chercher des patterns comme 16ABR, 04MAR, etc.)
        import re
        if re.search(r'\d{1,2}[A-Z]{3}', name):
            patterns["with_dates"].append(name)
        
        # Pattern commençant par DM
        if name.startswith("(DM)") or name.startswith("DM_"):
            patterns["dm_prefix"].append(name)
        
        # Pattern avec V1, V2, etc.
        if re.search(r'_V\d+', name):
            patterns["with_version"].append(name)
    
    # Afficher les patterns trouvés
    print("🔍 PATTERNS DÉTECTÉS:\n")
    
    for pattern_name, examples in patterns.items():
        if examples:
            print(f"📌 {pattern_name.replace('_', ' ').title()}: {len(examples)} annonces")
            for ex in examples[:3]:
                print(f"   • {ex}")
            if len(examples) > 3:
                print(f"   ... et {len(examples) - 3} autres")
            print()
    
    # Chercher spécifiquement le format attendu par Pablo
    pablo_format = []
    for ad in all_ad_names:
        name = ad["name"]
        # Format Pablo: angle_xxx|createur_xxx|format_xxx
        if "|" in name and name.count("|") >= 2:
            parts = name.split("|")
            if all("_" in part for part in parts):
                pablo_format.append(name)
    
    print("=" * 70)
    print("🎯 NOMENCLATURE PABLO (angle_xxx|créateur_xxx|format_xxx):\n")
    
    if pablo_format:
        print(f"✅ {len(pablo_format)} annonces suivent le format Pablo:")
        for name in pablo_format[:10]:
            print(f"   • {name}")
        if len(pablo_format) > 10:
            print(f"   ... et {len(pablo_format) - 10} autres")
    else:
        print("❌ AUCUNE annonce ne suit le format Pablo attendu!")
        print("   Format attendu: angle_xxx|créateur_xxx|format_xxx")
        print("   Formats trouvés: Principalement des noms avec underscores et dates")
    
    # Afficher tous les comptes pour référence
    print("\n" + "=" * 70)
    print("📋 COMPTES AVEC ANNONCES ACTIVES:\n")
    for i, account in enumerate(accounts_with_ads, 1):
        print(f"   {i}. {account}")

if __name__ == "__main__":
    extract_all_ad_names()