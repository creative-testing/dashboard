#!/usr/bin/env python3
"""
Vérifie les permissions du token et trouve les comptes avec des données
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

def check_token_permissions():
    """Vérifie quelles permissions on a avec ce token"""
    
    token = os.getenv("FB_TOKEN")
    
    print("🔍 VÉRIFICATION DES PERMISSIONS DU TOKEN")
    print("=" * 60)
    
    # 1. Vérifier les permissions du token
    debug_url = f"https://graph.facebook.com/v23.0/debug_token"
    debug_params = {
        "input_token": token,
        "access_token": token
    }
    
    response = requests.get(debug_url, params=debug_params)
    data = response.json()
    
    if "data" in data:
        token_data = data["data"]
        print("✅ Token valide!")
        print(f"   App ID: {token_data.get('app_id')}")
        print(f"   Type: {token_data.get('type')}")
        print(f"   Valide: {token_data.get('is_valid')}")
        
        scopes = token_data.get('scopes', [])
        print(f"\n📋 Permissions ({len(scopes)} total):")
        for scope in sorted(scopes)[:10]:  # Afficher les 10 premières
            print(f"   • {scope}")
        if len(scopes) > 10:
            print(f"   ... et {len(scopes) - 10} autres")
    
    print("\n" + "=" * 60)
    print("🔍 RECHERCHE DE COMPTES AVEC DES DONNÉES\n")
    
    # 2. Essayer de trouver des comptes avec des annonces
    accounts_url = f"https://graph.facebook.com/v23.0/me/adaccounts"
    params = {
        "access_token": token,
        "fields": "id,name,account_status,spend_cap,amount_spent,balance",
        "limit": 100
    }
    
    response = requests.get(accounts_url, params=params)
    accounts_data = response.json()
    
    if "data" in accounts_data:
        accounts = accounts_data["data"]
        
        # Filtrer les comptes qui ont dépensé de l'argent
        active_accounts = [
            acc for acc in accounts 
            if acc.get("account_status") == 1 and 
            float(acc.get("amount_spent", "0")) > 0
        ]
        
        print(f"✅ Comptes actifs avec historique de dépense: {len(active_accounts)}/{len(accounts)}")
        
        # Tester les 5 premiers comptes actifs
        for i, account in enumerate(active_accounts[:5], 1):
            account_id = account["id"]
            account_name = account.get("name", "Sans nom")
            amount_spent = account.get("amount_spent", "0")
            
            print(f"\n{i}. {account_name}")
            print(f"   ID: {account_id}")
            print(f"   Dépense totale: ${int(amount_spent)/100:.2f}")
            
            # Essayer de récupérer les campagnes
            campaigns_url = f"https://graph.facebook.com/v23.0/{account_id}/campaigns"
            camp_params = {
                "access_token": token,
                "fields": "name,status,objective",
                "limit": 5
            }
            
            camp_response = requests.get(campaigns_url, params=camp_params)
            camp_data = camp_response.json()
            
            if "data" in camp_data and camp_data["data"]:
                print(f"   ✅ {len(camp_data['data'])} campagnes trouvées")
                
                # Essayer de récupérer des insights
                insights_url = f"https://graph.facebook.com/v23.0/{account_id}/insights"
                insights_params = {
                    "access_token": token,
                    "level": "account",
                    "date_preset": "last_30_d",
                    "fields": "impressions,spend,clicks"
                }
                
                insights_response = requests.get(insights_url, params=insights_params)
                insights_data = insights_response.json()
                
                if "data" in insights_data and insights_data["data"]:
                    metrics = insights_data["data"][0]
                    print(f"   📊 Derniers 30 jours:")
                    print(f"      • Impressions: {metrics.get('impressions', 0):,}")
                    print(f"      • Dépense: ${metrics.get('spend', 0)}")
                    print(f"      • Clics: {metrics.get('clicks', 0):,}")
            else:
                print(f"   ⚠️ Pas de campagnes ou pas d'accès")

if __name__ == "__main__":
    check_token_permissions()