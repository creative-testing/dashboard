#!/usr/bin/env python3
"""
Script de diagnostic OAuth Facebook
Vérifie si les credentials fournis par Pablo sont suffisants et correctement configurés
"""
import requests
import sys
from urllib.parse import urlencode

# Credentials fournis par Pablo
APP_ID = "1496103148207058"
APP_SECRET = "1ef259878655b1b1a77389b493e3aa55"

# URL de callback à vérifier (à configurer dans l'app Facebook)
REDIRECT_URI = "http://localhost:8000/auth/facebook/callback"


def print_section(title):
    """Print une section avec des emojis"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def test_app_info():
    """
    Test 1: Récupérer les infos de l'app
    Vérifie que l'App ID et l'App Secret sont valides
    """
    print_section("🔍 TEST 1: Vérification App ID & Secret")

    # Générer un app access token
    url = "https://graph.facebook.com/oauth/access_token"
    params = {
        "client_id": APP_ID,
        "client_secret": APP_SECRET,
        "grant_type": "client_credentials"
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        app_token = data.get("access_token")
        if app_token:
            print("✅ App ID et App Secret sont VALIDES")
            print(f"   App Access Token: {app_token[:20]}...")
            return app_token
        else:
            print("❌ Impossible d'obtenir un token d'app")
            return None

    except requests.exceptions.RequestException as e:
        print(f"❌ ERREUR: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"   Réponse: {e.response.text}")
        return None


def test_app_details(app_token):
    """
    Test 2: Récupérer les détails de l'app
    Vérifie les permissions, le statut, etc.
    """
    print_section("📋 TEST 2: Détails de l'application")

    if not app_token:
        print("⏭️  Skipped (pas de token)")
        return

    url = f"https://graph.facebook.com/v23.0/{APP_ID}"
    params = {
        "fields": "name,link,category,subcategory,app_domains,privacy_policy_url,terms_of_service_url",
        "access_token": app_token
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        print("ℹ️  Informations de l'app:")
        for key, value in data.items():
            print(f"   - {key}: {value}")

        # Vérifier Privacy Policy (requis pour App Review)
        if data.get("privacy_policy_url"):
            print("\n✅ Privacy Policy URL configurée")
        else:
            print("\n⚠️  Privacy Policy URL MANQUANTE (requis pour App Review)")

        return data

    except requests.exceptions.RequestException as e:
        print(f"❌ ERREUR: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"   Réponse: {e.response.text}")
        return None


def test_permissions():
    """
    Test 3: Vérifier quelles permissions sont demandées
    """
    print_section("🔐 TEST 3: Permissions requises")

    print("ℹ️  Permissions à demander pour le SaaS:")
    print("   - ads_read (lecture des ads)")
    print("   - business_management (gestion business)")
    print()
    print("📝 Ces permissions doivent être configurées dans l'app Facebook:")
    print(f"   👉 https://developers.facebook.com/apps/{APP_ID}/app-review/permissions/")
    print()
    print("⚠️  Note: Certaines permissions nécessitent App Review (validation Meta)")


def generate_oauth_url():
    """
    Test 4: Générer l'URL OAuth pour tester le flux
    """
    print_section("🔗 TEST 4: URL OAuth générée")

    oauth_params = {
        "client_id": APP_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": "ads_read,business_management",
        "response_type": "code",
        "state": "test_state_123"
    }

    oauth_url = f"https://www.facebook.com/v23.0/dialog/oauth?{urlencode(oauth_params)}"

    print("✅ URL OAuth générée:")
    print(f"   {oauth_url}")
    print()
    print("📋 Pour tester manuellement:")
    print("   1. Ouvre cette URL dans ton navigateur")
    print("   2. Connecte-toi avec un compte Facebook")
    print("   3. Autorise l'app")
    print("   4. Tu seras redirigé vers:", REDIRECT_URI)
    print()
    print("⚠️  IMPORTANT: Le redirect URI doit être configuré dans l'app:")
    print(f"   👉 https://developers.facebook.com/apps/{APP_ID}/fb-login/settings/")
    print(f"   Ajoute dans 'Valid OAuth Redirect URIs': {REDIRECT_URI}")

    return oauth_url


def test_redirect_uri_configured():
    """
    Test 5: Vérifier si le redirect URI est configuré (indirect)
    """
    print_section("🎯 TEST 5: Configuration Redirect URI")

    print("⚠️  À VÉRIFIER MANUELLEMENT:")
    print()
    print(f"   1. Va sur https://developers.facebook.com/apps/{APP_ID}/fb-login/settings/")
    print("   2. Dans 'Valid OAuth Redirect URIs', ajoute:")
    print(f"      → {REDIRECT_URI}")
    print("      → https://ton-domaine.com/auth/facebook/callback (pour prod)")
    print()
    print("   3. Active 'Strict Mode for Redirect URIs' (sécurité)")
    print()
    print("   4. Sauvegarde")


def check_existing_token():
    """
    Test 6: Si tu as déjà un User Access Token, on peut tester les ad accounts
    """
    print_section("🧪 TEST 6: Test avec User Access Token (optionnel)")

    print("ℹ️  Si tu as déjà un User Access Token, on peut tester:")
    print()
    print("   1. Récupérer /me/adaccounts")
    print("   2. Vérifier les permissions accordées")
    print()
    print("📝 Pour obtenir un token de test:")
    print(f"   👉 https://developers.facebook.com/tools/accesstoken/")
    print(f"   OU utilise l'URL OAuth générée au TEST 4")
    print()
    user_token = input("   Colle un User Access Token (ou ENTER pour skip): ").strip()

    if not user_token:
        print("   ⏭️  Skipped")
        return

    # Tester /me
    try:
        response = requests.get(
            "https://graph.facebook.com/v23.0/me",
            params={"access_token": user_token},
            timeout=10
        )
        response.raise_for_status()
        user_data = response.json()
        print(f"\n✅ Token valide! User: {user_data.get('name')} (ID: {user_data.get('id')})")

        # Tester /me/adaccounts
        response = requests.get(
            "https://graph.facebook.com/v23.0/me/adaccounts",
            params={
                "access_token": user_token,
                "fields": "id,name,account_status"
            },
            timeout=10
        )
        response.raise_for_status()
        accounts_data = response.json()

        accounts = accounts_data.get("data", [])
        print(f"\n✅ Ad Accounts trouvés: {len(accounts)}")
        for acc in accounts[:5]:  # Afficher les 5 premiers
            print(f"   - {acc.get('name')} (ID: {acc.get('id')})")

        if len(accounts) > 5:
            print(f"   ... et {len(accounts) - 5} autres")

        return True

    except requests.exceptions.RequestException as e:
        print(f"\n❌ ERREUR avec le token: {e}")
        if hasattr(e, 'response') and e.response is not None:
            error_data = e.response.json()
            print(f"   Message: {error_data.get('error', {}).get('message')}")
        return False


def main():
    """Point d'entrée principal"""
    print("\n" + "="*60)
    print("  🧪 DIAGNOSTIC OAUTH FACEBOOK - CREATIVE TESTING SAAS")
    print("="*60)
    print()
    print("📋 Ce script vérifie si les credentials fournis par Pablo")
    print("   sont suffisants pour implémenter l'OAuth SaaS.")
    print()

    # Test 1: Vérifier App ID & Secret
    app_token = test_app_info()

    # Test 2: Détails de l'app
    app_details = test_app_details(app_token)

    # Test 3: Permissions
    test_permissions()

    # Test 4: Générer URL OAuth
    oauth_url = generate_oauth_url()

    # Test 5: Config Redirect URI
    test_redirect_uri_configured()

    # Test 6: Test avec token utilisateur (optionnel)
    check_existing_token()

    # Résumé final
    print_section("📊 RÉSUMÉ")

    print("✅ CE QUI FONCTIONNE:")
    if app_token:
        print("   - App ID et App Secret sont valides")
        print("   - On peut générer des URLs OAuth")
        print("   - L'app existe et est accessible")
    else:
        print("   ❌ Les credentials ne fonctionnent pas!")

    print()
    print("⚠️  À CONFIGURER DANS L'APP FACEBOOK:")
    print("   1. Valid OAuth Redirect URIs")
    print("   2. Privacy Policy URL (si pas fait)")
    print("   3. Activer les permissions ads_read + business_management")
    print()
    print("🎯 PROCHAINES ÉTAPES:")
    print("   1. Configure les Redirect URIs dans l'app Facebook")
    print("   2. Teste le flux OAuth avec l'URL générée")
    print("   3. Si ça marche → on peut implémenter dans l'API!")
    print()
    print("📚 Liens utiles:")
    print(f"   - Settings: https://developers.facebook.com/apps/{APP_ID}/settings/basic/")
    print(f"   - Facebook Login: https://developers.facebook.com/apps/{APP_ID}/fb-login/settings/")
    print(f"   - Permissions: https://developers.facebook.com/apps/{APP_ID}/app-review/permissions/")
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏹️  Interrompu par l'utilisateur")
        sys.exit(0)
