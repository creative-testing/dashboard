#!/usr/bin/env python3
"""
Script de debug pour comprendre les erreurs
"""
import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

token = os.getenv("FACEBOOK_ACCESS_TOKEN")
print("🔍 TEST DE DEBUG\n" + "="*50)

# 1. Test basique - le token marche?
print("\n1️⃣ Test token...")
url = "https://graph.facebook.com/v23.0/me"
response = requests.get(url, params={"access_token": token})
if response.status_code == 200:
    print("✅ Token valide")
else:
    print(f"❌ Token invalide: {response.status_code}")
    print(response.json())
    exit(1)

# 2. Test simple sans breakdown sur UN compte qui marchait
print("\n2️⃣ Test SANS démographies sur Essentiasl Mx...")
url = "https://graph.facebook.com/v23.0/act_186473512/insights"
params = {
    "access_token": token,
    "level": "ad",
    "time_range": '{"since":"2025-08-25","until":"2025-08-26"}',
    "fields": "ad_id,ad_name,impressions,spend",
    "limit": 5
}
response = requests.get(url, params=params, timeout=30)
if response.status_code == 200:
    data = response.json()
    count = len(data.get("data", []))
    print(f"✅ Sans breakdown: {count} lignes")
else:
    print(f"❌ Erreur {response.status_code}: {response.json()}")

# 3. Test AVEC breakdown age,gender
print("\n3️⃣ Test AVEC démographies sur Essentiasl Mx...")
params["breakdowns"] = "age,gender"
response = requests.get(url, params=params, timeout=30)
if response.status_code == 200:
    data = response.json()
    count = len(data.get("data", []))
    print(f"✅ Avec breakdown: {count} lignes")
else:
    print(f"❌ Erreur {response.status_code}: {response.json()}")

# 4. Test sur un compte qui a eu erreur 500
print("\n4️⃣ Test sur compte problématique (VITDAYMX)...")
url = "https://graph.facebook.com/v23.0/act_1130232357338784/insights"
params = {
    "access_token": token,
    "level": "ad",
    "time_range": '{"since":"2025-08-25","until":"2025-08-26"}',
    "fields": "ad_id,impressions,spend",
    "limit": 5
}

# D'abord sans breakdown
response = requests.get(url, params=params, timeout=30)
if response.status_code == 200:
    count = len(response.json().get("data", []))
    print(f"  Sans breakdown: {count} lignes")
    
    # Puis avec breakdown
    params["breakdowns"] = "age,gender"
    response = requests.get(url, params=params, timeout=30)
    if response.status_code == 200:
        count = len(response.json().get("data", []))
        print(f"  ✅ Avec breakdown: {count} lignes")
    else:
        print(f"  ❌ Avec breakdown: Erreur {response.status_code}")
        error_data = response.json()
        if "error" in error_data:
            print(f"     Message: {error_data['error'].get('message', 'Unknown')}")
else:
    print(f"  ❌ Sans breakdown: Erreur {response.status_code}")

print("\n" + "="*50)
print("📊 DIAGNOSTIC:")
print("Si erreur avec breakdown mais pas sans → problème de permissions")
print("Si erreur dans les deux cas → problème de compte ou token")