"""
🧪 TEST LOCAL - Pagination Meta API
Compare version buggée (sans pagination) vs version fixée (avec pagination)
Utilise le token production depuis .env - AUCUN RISQUE, juste lecture
"""
import asyncio
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("FACEBOOK_ACCESS_TOKEN")
API_VERSION = os.getenv("META_API_VERSION", "v23.0")

if not TOKEN:
    print("❌ FACEBOOK_ACCESS_TOKEN manquant dans .env")
    exit(1)


async def test_version_buggee():
    """
    Version actuelle (sans pagination) - devrait retourner 25 max
    Simule le comportement actuel de meta_client.get_ad_accounts()
    """
    url = f"https://graph.facebook.com/{API_VERSION}/me/adaccounts"
    params = {
        "access_token": TOKEN,
        "fields": "id,name,account_status",
        # PAS de limit → Meta utilise défaut (25)
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        accounts = data.get("data", [])

        has_next = "paging" in data and "next" in data.get("paging", {})

        print(f"🐛 VERSION BUGGÉE (sans pagination):")
        print(f"   Comptes retournés: {len(accounts)}")
        print(f"   Paging.next existe? {'OUI ⚠️' if has_next else 'NON'}")
        if has_next:
            print(f"   → IL Y A PLUS DE COMPTES DISPONIBLES !")
        return accounts


async def test_version_fixee():
    """
    Version fixée (avec pagination) - devrait retourner TOUS
    Simule le fix proposé
    """
    url = f"https://graph.facebook.com/{API_VERSION}/me/adaccounts"
    params = {
        "access_token": TOKEN,
        "fields": "id,name,account_status",
        "limit": 100,  # ✅ Max par page
    }

    all_accounts = []
    next_url = url
    page_count = 0

    async with httpx.AsyncClient(timeout=30.0) as client:
        while next_url and page_count < 50:
            response = await client.get(next_url, params=params if params else None)
            response.raise_for_status()
            data = response.json()

            all_accounts.extend(data.get("data", []))

            # Next page?
            if "paging" in data and "next" in data["paging"]:
                next_url = data["paging"]["next"]
                params = None  # Next URL contient déjà les params
                page_count += 1
            else:
                break

        print(f"✅ VERSION FIXÉE (avec pagination):")
        print(f"   Comptes retournés: {len(all_accounts)}")
        print(f"   Pages parcourues: {page_count + 1}")
        return all_accounts


async def main():
    print("=" * 60)
    print("🧪 TEST DE PAGINATION META API - ENVIRONNEMENT PRODUCTION")
    print("=" * 60)
    print()

    try:
        buggee = await test_version_buggee()
        print()
        fixee = await test_version_fixee()
        print()

        print("=" * 60)
        print("📊 RÉSULTAT COMPARAISON:")
        print("=" * 60)
        print(f"   Version buggée:  {len(buggee)} comptes")
        print(f"   Version fixée:   {len(fixee)} comptes")
        print(f"   Différence:      {len(fixee) - len(buggee)} comptes manquants")
        print()

        if len(fixee) > len(buggee):
            print("🎯 BUG CONFIRMÉ ! Le fix récupère plus de comptes.")
            print()
            print("Comptes manquants (premiers 10) :")
            missing = [acc for acc in fixee if acc not in buggee]
            for i, acc in enumerate(missing[:10], 1):
                print(f"   {i}. {acc['name']} ({acc['id']})")
            if len(missing) > 10:
                print(f"   ... et {len(missing) - 10} autres")
            print()
            print("✅ RECOMMANDATION: Déployer le fix immédiatement")
        else:
            print("🤔 Pas de différence détectée")
            print("   Possibilités:")
            print("   - Total comptes < 100 (pas de pagination nécessaire)")
            print("   - Bug n'existe pas pour ce compte")

        print()
        print("Premiers 5 comptes (version fixée):")
        for i, acc in enumerate(fixee[:5], 1):
            print(f"   {i}. {acc['name']} ({acc['id']})")

    except Exception as e:
        print(f"❌ ERREUR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
