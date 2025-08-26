#!/usr/bin/env python3
"""
Script de test pour vérifier la connexion à l'API Meta
et lister les comptes publicitaires disponibles
"""
import requests
import json
from dotenv import load_dotenv
import os

# Charger les variables d'environnement
load_dotenv()

def test_token_and_list_accounts():
    """Teste le token et liste les comptes publicitaires accessibles"""
    
    token = os.getenv("FB_TOKEN")
    if not token:
        print("❌ FB_TOKEN non trouvé dans .env")
        return
    
    print("🔍 Test du token Meta/Facebook...")
    print(f"Token (premiers caractères): {token[:20]}...")
    
    # 1. Vérifier le token en récupérant les infos utilisateur
    url = "https://graph.facebook.com/v23.0/me"
    params = {
        "access_token": token,
        "fields": "id,name"
    }
    
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            user_data = response.json()
            print(f"✅ Token valide ! Utilisateur: {user_data.get('name', 'N/A')} (ID: {user_data.get('id', 'N/A')})")
        else:
            print(f"❌ Erreur token: {response.status_code}")
            print(f"Réponse: {response.text}")
            return
    except Exception as e:
        print(f"❌ Erreur de connexion: {e}")
        return
    
    # 2. Lister les comptes publicitaires
    print("\n📊 Comptes publicitaires accessibles:")
    print("-" * 50)
    
    url = "https://graph.facebook.com/v23.0/me/adaccounts"
    params = {
        "access_token": token,
        "fields": "id,name,account_id,account_status,currency,timezone_name,amount_spent"
    }
    
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            accounts = data.get("data", [])
            
            if accounts:
                for i, account in enumerate(accounts, 1):
                    status = "✅ Actif" if account.get("account_status") == 1 else "⚠️ Inactif"
                    print(f"\n{i}. {account.get('name', 'Sans nom')}")
                    print(f"   ID: {account.get('id')}")
                    print(f"   Statut: {status}")
                    print(f"   Devise: {account.get('currency', 'N/A')}")
                    print(f"   Fuseau: {account.get('timezone_name', 'N/A')}")
                    
                    # Essayer de récupérer quelques stats
                    if account.get("account_status") == 1:
                        test_account_insights(account.get("id"), token)
                
                print(f"\n✅ Total: {len(accounts)} compte(s) trouvé(s)")
                
                # Suggérer l'ID à utiliser
                active_accounts = [a for a in accounts if a.get("account_status") == 1]
                if active_accounts:
                    suggested_id = active_accounts[0].get("id")
                    print(f"\n💡 Suggestion: Ajoutez cette ligne dans votre .env:")
                    print(f"   META_ACCOUNT_ID={suggested_id}")
            else:
                print("⚠️ Aucun compte publicitaire trouvé avec ce token")
        else:
            print(f"❌ Erreur lors de la récupération des comptes: {response.status_code}")
            print(f"Réponse: {response.text}")
            
    except Exception as e:
        print(f"❌ Erreur: {e}")


def test_account_insights(account_id, token):
    """Teste la récupération des insights pour un compte"""
    print(f"\n   📈 Test des insights pour ce compte...")
    
    url = f"https://graph.facebook.com/v23.0/{account_id}/insights"
    params = {
        "access_token": token,
        "level": "ad",
        "date_preset": "last_7_d",
        "fields": "ad_name,spend,impressions",
        "limit": 1,
        "filtering": json.dumps([{"field": "ad.effective_status", "operator": "EQUAL", "value": "ACTIVE"}])
    }
    
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            ads = data.get("data", [])
            if ads:
                print(f"   ✅ {len(ads)} annonce(s) active(s) trouvée(s)")
                print(f"   Exemple: {ads[0].get('ad_name', 'N/A')} - Dépense: {ads[0].get('spend', 0)}")
            else:
                print(f"   ⚠️ Aucune annonce active dans les 7 derniers jours")
    except:
        pass


if __name__ == "__main__":
    test_token_and_list_accounts()