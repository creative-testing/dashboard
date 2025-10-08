"""
Test script pour l'endpoint de proxy de fichiers
"""
import requests
from uuid import UUID
from app.utils.jwt import create_access_token

# Credentials du dernier OAuth réussi
TENANT_ID = "4e2b8463-0848-4fd7-92ea-980342b3d038"
USER_ID = "2625fe67-f229-46dc-8e57-c3b91f9403d8"
ACCOUNT_ID = "act_386980458908639"

def test_file_proxy():
    """Test l'endpoint de proxy pour servir les fichiers optimisés"""

    # Générer un JWT
    print("🔐 Generating JWT...")
    access_token = create_access_token(
        user_id=UUID(USER_ID),
        tenant_id=UUID(TENANT_ID)
    )

    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    # Tester les 3 fichiers
    files_to_test = ["meta_v1.json", "agg_v1.json", "summary_v1.json"]

    for filename in files_to_test:
        print(f"\n📡 Fetching {filename}...")
        response = requests.get(
            f"http://localhost:8000/api/data/files/{ACCOUNT_ID}/{filename}",
            headers=headers
        )

        if response.status_code == 200:
            data = response.json()
            print(f"✅ {filename} loaded successfully")
            if filename == "summary_v1.json":
                print(f"   Content: {data}")
        else:
            print(f"❌ Failed to load {filename}: {response.status_code}")
            print(f"   Error: {response.text}")

    print("\n✅ File proxy test completed!")

if __name__ == "__main__":
    test_file_proxy()
