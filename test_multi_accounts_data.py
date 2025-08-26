#!/usr/bin/env python3
"""
Test de récupération des données depuis PLUSIEURS comptes
avec le token unique FB_TOKEN qui a accès à 64 comptes
"""
import os
import requests
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

def test_multi_accounts_insights():
    """Récupère les insights des derniers 7 jours depuis TOUS les comptes"""
    
    token = os.getenv("FB_TOKEN")
    
    print("🚀 TEST MULTI-COMPTES - Récupération des données")
    print("=" * 60)
    
    # D'abord, récupérer la liste des comptes
    accounts_url = f"https://graph.facebook.com/v23.0/me/adaccounts"
    params = {
        "access_token": token,
        "fields": "id,name,account_status",
        "limit": 100
    }
    
    response = requests.get(accounts_url, params=params)
    data = response.json()
    
    if "error" in data:
        print(f"❌ Erreur: {data['error']['message']}")
        return
        
    accounts = data.get("data", [])
    print(f"✅ {len(accounts)} comptes trouvés\n")
    
    # Pour chaque compte actif, récupérer les insights
    total_ads = 0
    accounts_with_ads = []
    
    for i, account in enumerate(accounts[:10], 1):  # Tester les 10 premiers
        account_id = account["id"]
        account_name = account.get("name", "Sans nom")
        account_status = account.get("account_status", 0)
        
        # Ne traiter que les comptes actifs (status = 1)
        if account_status != 1:
            continue
            
        print(f"{i}. Compte: {account_name}")
        print(f"   ID: {account_id}")
        
        # Récupérer les insights du compte
        insights_url = f"https://graph.facebook.com/v23.0/{account_id}/insights"
        insights_params = {
            "access_token": token,
            "level": "ad",
            "date_preset": "last_7_d",
            "fields": "ad_name,impressions,spend,ctr,cpm",
            "limit": 5,  # Juste 5 ads par compte pour le test
            "filtering": "[{'field':'impressions','operator':'GREATER_THAN','value':'0'}]"
        }
        
        try:
            insights_response = requests.get(insights_url, params=insights_params)
            insights_data = insights_response.json()
            
            if "error" in insights_data:
                print(f"   ⚠️ Pas d'accès aux données")
            else:
                ads = insights_data.get("data", [])
                if ads:
                    print(f"   ✅ {len(ads)} annonces actives")
                    accounts_with_ads.append({
                        "name": account_name,
                        "id": account_id,
                        "ads_count": len(ads)
                    })
                    total_ads += len(ads)
                    
                    # Afficher une annonce exemple
                    if ads:
                        sample = ads[0]
                        print(f"   📊 Exemple: {sample.get('ad_name', 'Sans nom')}")
                        print(f"      • Impressions: {sample.get('impressions', 0)}")
                        print(f"      • Dépense: ${sample.get('spend', 0)}")
                else:
                    print(f"   💤 Aucune annonce active")
        except Exception as e:
            print(f"   ❌ Erreur: {e}")
        
        print()
    
    # Résumé
    print("\n" + "=" * 60)
    print("📊 RÉSUMÉ MULTI-COMPTES:")
    print(f"  • Comptes testés: 10")
    print(f"  • Comptes avec annonces: {len(accounts_with_ads)}")
    print(f"  • Total annonces trouvées: {total_ads}")
    
    if accounts_with_ads:
        print("\n📈 Top comptes avec annonces:")
        for acc in sorted(accounts_with_ads, key=lambda x: x['ads_count'], reverse=True)[:5]:
            print(f"  • {acc['name']}: {acc['ads_count']} annonces")

if __name__ == "__main__":
    test_multi_accounts_insights()