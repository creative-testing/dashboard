#!/usr/bin/env python3
"""
Test rapide de tous les comptes pour voir lesquels marchent
"""
import os
import requests
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed

load_dotenv()

token = os.getenv("FACEBOOK_ACCESS_TOKEN")

def test_account(account):
    """Test si on peut accéder aux insights d'un compte"""
    account_id = account["id"]
    account_name = account.get("name", "Unknown")
    
    url = f"https://graph.facebook.com/v23.0/{account_id}/insights"
    params = {
        "access_token": token,
        "level": "ad",
        "time_range": '{"since":"2025-08-25","until":"2025-08-26"}',
        "fields": "ad_id",
        "limit": 1
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            has_data = len(data.get("data", [])) > 0
            return (account_name, "OK", has_data)
        else:
            return (account_name, f"ERROR_{response.status_code}", False)
    except:
        return (account_name, "TIMEOUT", False)

print("🔍 TEST DE TOUS LES COMPTES")
print("="*60)

# Récupérer tous les comptes
url = "https://graph.facebook.com/v23.0/me/adaccounts"
params = {
    "access_token": token,
    "fields": "id,name,account_status",
    "limit": 200
}

response = requests.get(url, params=params, timeout=30)
accounts = response.json().get("data", [])
active_accounts = [acc for acc in accounts if acc.get("account_status") == 1]

print(f"📊 {len(active_accounts)} comptes actifs à tester\n")

# Tester en parallèle
working_accounts = []
error_accounts = []

with ThreadPoolExecutor(max_workers=20) as executor:
    futures = [executor.submit(test_account, acc) for acc in active_accounts]
    
    for future in as_completed(futures):
        name, status, has_data = future.result()
        if status == "OK":
            working_accounts.append((name, has_data))
            if has_data:
                print(f"✅ {name[:30]:30} OK avec données")
            else:
                print(f"✅ {name[:30]:30} OK mais vide")
        else:
            error_accounts.append((name, status))
            print(f"❌ {name[:30]:30} {status}")

print("\n" + "="*60)
print(f"📊 RÉSUMÉ:")
print(f"✅ {len(working_accounts)} comptes accessibles")
print(f"   - {sum(1 for _, has_data in working_accounts if has_data)} avec des données")
print(f"   - {sum(1 for _, has_data in working_accounts if not has_data)} vides")
print(f"❌ {len(error_accounts)} comptes en erreur")

# Afficher les erreurs par type
from collections import Counter
error_types = Counter(status for _, status in error_accounts)
for error_type, count in error_types.most_common():
    print(f"   - {error_type}: {count} comptes")