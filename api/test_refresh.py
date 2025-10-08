"""
Test script pour l'endpoint de refresh
"""
import asyncio
import requests
import sys
from uuid import UUID
from app.utils.jwt import create_access_token
from pathlib import Path

# Credentials du dernier OAuth réussi (d'après les logs)
TENANT_ID = "4e2b8463-0848-4fd7-92ea-980342b3d038"
USER_ID = "2625fe67-f229-46dc-8e57-c3b91f9403d8"
ACCOUNT_ID = "act_386980458908639"

def test_refresh():
    """Test l'endpoint de refresh"""

    # 1. Générer un JWT
    print("🔐 Generating JWT...")
    access_token = create_access_token(
        user_id=UUID(USER_ID),
        tenant_id=UUID(TENANT_ID)
    )
    print(f"✅ JWT generated: {access_token[:50]}...")

    # 2. Appeler l'endpoint refresh
    print(f"\n📡 Calling POST /api/accounts/refresh/{ACCOUNT_ID}...")
    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    response = requests.post(
        f"http://localhost:8000/api/accounts/refresh/{ACCOUNT_ID}",
        headers=headers
    )

    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")

    if response.status_code != 200:
        print("❌ Refresh failed!")
        sys.exit(1)

    result = response.json()

    # 3. Vérifier les fichiers générés
    print("\n📁 Checking generated files...")
    data_root = Path("./data")
    files_to_check = [
        f"tenants/{TENANT_ID}/accounts/{ACCOUNT_ID}/meta_v1.json",
        f"tenants/{TENANT_ID}/accounts/{ACCOUNT_ID}/agg_v1.json",
        f"tenants/{TENANT_ID}/accounts/{ACCOUNT_ID}/summary_v1.json",
    ]

    for file_path in files_to_check:
        full_path = data_root / file_path
        if full_path.exists():
            print(f"✅ {file_path} exists ({full_path.stat().st_size} bytes)")
        else:
            print(f"❌ {file_path} NOT FOUND")

    print("\n✅ Refresh test completed successfully!")
    print(f"📊 Stats: {result['ads_fetched']} ads fetched, {len(result['files_written'])} files written")

if __name__ == "__main__":
    test_refresh()
