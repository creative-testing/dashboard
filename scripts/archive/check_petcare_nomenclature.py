#!/usr/bin/env python3
"""
Vérification spécifique du compte Petcare et modifications récentes
"""
import os
import requests
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

def check_petcare_specifically():
    """Check spécifiquement Petcare + modifications aujourd'hui"""
    
    token = os.getenv("FB_TOKEN")
    
    print("🔍 VÉRIFICATION SPÉCIFIQUE PETCARE")
    print("=" * 60)
    
    # Trouver le compte Petcare
    accounts_url = "https://graph.facebook.com/v23.0/me/adaccounts"
    response = requests.get(accounts_url, params={
        "access_token": token,
        "fields": "id,name,account_status",
        "limit": 100
    })
    
    accounts = response.json().get("data", [])
    
    # Chercher Petcare
    petcare_accounts = []
    for acc in accounts:
        name = acc.get("name", "").lower()
        if "petcare" in name:
            petcare_accounts.append(acc)
    
    print(f"🎯 Comptes Petcare trouvés: {len(petcare_accounts)}")
    for acc in petcare_accounts:
        print(f"  • {acc['name']} (ID: {acc['id']})")
    
    if not petcare_accounts:
        print("❌ Aucun compte Petcare trouvé")
        return []
    
    # Analyser chaque compte Petcare
    all_petcare_ads = []
    
    for account in petcare_accounts:
        account_id = account["id"]
        account_name = account["name"]
        
        print(f"\n📊 Analyse {account_name}...")
        
        try:
            # Récupérer TOUTES les annonces (pas juste actives)
            ads_url = f"https://graph.facebook.com/v23.0/{account_id}/ads"
            params = {
                "access_token": token,
                "fields": "id,name,effective_status,created_time,updated_time",
                "limit": 200
            }
            
            response = requests.get(ads_url, params=params)
            data = response.json()
            
            if "data" in data:
                ads = data["data"]
                
                print(f"   Total annonces: {len(ads)}")
                
                # Analyser par date de modification
                today = datetime.now().strftime('%Y-%m-%d')
                recent_ads = []
                
                for ad in ads:
                    updated = ad.get("updated_time", "")
                    if updated and updated.startswith(today):
                        recent_ads.append(ad)
                
                print(f"   Modifiées aujourd'hui: {len(recent_ads)}")
                
                # Afficher échantillon récent
                if recent_ads:
                    print(f"\n   📝 ANNONCES MODIFIÉES AUJOURD'HUI:")
                    for i, ad in enumerate(recent_ads[:10], 1):
                        status = ad.get("effective_status", "N/A")
                        updated = ad.get("updated_time", "")[:16] if ad.get("updated_time") else "N/A"
                        print(f"     {i:2}. {ad['name'][:60]:60} [{status}, {updated}]")
                else:
                    print("   ❌ Aucune modification aujourd'hui détectée")
                
                # Afficher aussi quelques annonces actives récentes
                active_ads = [ad for ad in ads if ad.get("effective_status") == "ACTIVE"][:10]
                if active_ads:
                    print(f"\n   ⚡ ANNONCES ACTIVES (échantillon):")
                    for i, ad in enumerate(active_ads, 1):
                        created = ad.get("created_time", "")[:10] if ad.get("created_time") else "N/A"
                        print(f"     {i:2}. {ad['name'][:60]:60} [Créée: {created}]")
                
                all_petcare_ads.extend(ads)
                
            else:
                print(f"   ❌ Erreur récupération: {data}")
                
        except Exception as e:
            print(f"   ❌ Erreur: {e}")
    
    return all_petcare_ads

if __name__ == "__main__":
    ads = check_petcare_specifically()
    
    if ads:
        print(f"\n✅ {len(ads)} annonces Petcare analysées")
        print("🎯 Prochaine étape: Parser la nomenclature si détectée")
    else:
        print("\n❌ Aucune donnée Petcare récupérée")