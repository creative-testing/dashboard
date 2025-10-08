#!/usr/bin/env python3
"""
Script de test ultra-simple pour vérifier un User Access Token
Teste si on peut vraiment récupérer les ad accounts d'un utilisateur
"""
import requests
import sys
from typing import Dict, List

# Credentials de l'app
APP_ID = "1496103148207058"
APP_SECRET = "1ef259878655b1b1a77389b493e3aa55"


def print_section(title: str):
    """Print une section avec séparation"""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")


def test_token_validity(token: str) -> Dict:
    """
    Vérifie si le token est valide et récupère les infos utilisateur

    Returns:
        Dict avec les infos user si valide, sinon None
    """
    print_section("🔍 TEST 1: Validité du token")

    try:
        response = requests.get(
            "https://graph.facebook.com/v23.0/me",
            params={"access_token": token},
            timeout=10
        )
        response.raise_for_status()
        user_data = response.json()

        print(f"✅ Token VALIDE!")
        print(f"   User: {user_data.get('name', 'N/A')}")
        print(f"   User ID: {user_data.get('id', 'N/A')}")

        return user_data

    except requests.exceptions.RequestException as e:
        print(f"❌ ERREUR: Le token n'est pas valide ou a expiré")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_data = e.response.json()
                print(f"   Message: {error_data.get('error', {}).get('message')}")
                print(f"   Code: {error_data.get('error', {}).get('code')}")
            except:
                print(f"   Réponse: {e.response.text}")
        return None


def test_token_permissions(token: str) -> List[str]:
    """
    Récupère les permissions accordées au token

    Returns:
        Liste des permissions accordées
    """
    print_section("🔐 TEST 2: Permissions du token")

    try:
        response = requests.get(
            "https://graph.facebook.com/v23.0/me/permissions",
            params={"access_token": token},
            timeout=10
        )
        response.raise_for_status()
        perms_data = response.json()

        granted_perms = [
            p['permission']
            for p in perms_data.get('data', [])
            if p.get('status') == 'granted'
        ]

        print(f"✅ Permissions accordées: {len(granted_perms)}")
        for perm in granted_perms:
            print(f"   • {perm}")

        # Vérifier les permissions critiques pour le SaaS
        required_perms = ['ads_read', 'business_management']
        missing_perms = [p for p in required_perms if p not in granted_perms]

        if missing_perms:
            print(f"\n⚠️  Permissions MANQUANTES pour le SaaS:")
            for perm in missing_perms:
                print(f"   ✗ {perm}")
        else:
            print(f"\n✅ Toutes les permissions nécessaires sont présentes!")

        return granted_perms

    except requests.exceptions.RequestException as e:
        print(f"❌ ERREUR lors de la récupération des permissions")
        if hasattr(e, 'response') and e.response is not None:
            print(f"   Réponse: {e.response.text}")
        return []


def test_ad_accounts(token: str) -> List[Dict]:
    """
    Teste l'accès aux ad accounts de l'utilisateur
    C'est le test CRITIQUE pour savoir si le SaaS peut fonctionner

    Returns:
        Liste des ad accounts trouvés
    """
    print_section("🎯 TEST 3: Accès aux Ad Accounts (CRITIQUE)")

    try:
        response = requests.get(
            "https://graph.facebook.com/v23.0/me/adaccounts",
            params={
                "access_token": token,
                "fields": "id,name,account_status,currency,timezone_name"
            },
            timeout=10
        )
        response.raise_for_status()
        accounts_data = response.json()

        accounts = accounts_data.get('data', [])

        if not accounts:
            print("⚠️  Aucun ad account trouvé")
            print("   Cela peut signifier:")
            print("   • L'utilisateur n'a pas de comptes publicitaires")
            print("   • Les permissions sont insuffisantes")
            print("   • L'app n'a pas été approuvée pour ces permissions")
            return []

        print(f"✅ Ad Accounts trouvés: {len(accounts)}")
        print()
        for acc in accounts[:10]:  # Afficher max 10
            status = acc.get('account_status', 'N/A')
            status_emoji = "✓" if status == 1 else "⚠"
            print(f"   {status_emoji} {acc.get('name', 'N/A')}")
            print(f"      ID: {acc.get('id')}")
            print(f"      Currency: {acc.get('currency', 'N/A')}")
            print(f"      Status: {status}")
            print(f"      Timezone: {acc.get('timezone_name', 'N/A')}")
            print()

        if len(accounts) > 10:
            print(f"   ... et {len(accounts) - 10} autres comptes")

        return accounts

    except requests.exceptions.RequestException as e:
        print(f"❌ ERREUR lors de l'accès aux ad accounts")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_data = e.response.json()
                error_msg = error_data.get('error', {}).get('message', 'N/A')
                error_code = error_data.get('error', {}).get('code', 'N/A')

                print(f"   Message: {error_msg}")
                print(f"   Code: {error_code}")

                if 'permissions' in error_msg.lower():
                    print()
                    print("   💡 Cela signifie probablement:")
                    print("      • L'app n'a pas demandé les bonnes permissions")
                    print("      • Ou les permissions n'ont pas été approuvées (App Review)")

            except:
                print(f"   Réponse: {e.response.text}")
        return []


def test_insights_sample(token: str, account_id: str):
    """
    Teste si on peut récupérer des insights pour un compte
    C'est ce que le SaaS fera en production
    """
    print_section("📊 TEST 4: Accès aux Insights (données réelles)")

    try:
        # Tester un call simple d'insights (dernières 7 jours)
        response = requests.get(
            f"https://graph.facebook.com/v23.0/{account_id}/insights",
            params={
                "access_token": token,
                "fields": "account_id,account_name,impressions,spend",
                "time_range": "{'since':'2025-09-28','until':'2025-10-05'}",
                "limit": 1
            },
            timeout=10
        )
        response.raise_for_status()
        insights_data = response.json()

        data = insights_data.get('data', [])

        if data:
            print(f"✅ Insights récupérés avec succès!")
            print(f"   Account: {data[0].get('account_name', 'N/A')}")
            print(f"   Impressions: {data[0].get('impressions', 'N/A')}")
            print(f"   Spend: {data[0].get('spend', 'N/A')}")
        else:
            print("⚠️  Aucune donnée insights (peut-être pas de dépenses récentes)")

    except requests.exceptions.RequestException as e:
        print(f"⚠️  Impossible de récupérer les insights")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_data = e.response.json()
                print(f"   Message: {error_data.get('error', {}).get('message')}")
            except:
                print(f"   Réponse: {e.response.text}")


def main():
    """Point d'entrée principal"""
    print("\n" + "="*70)
    print("  🧪 TEST USER ACCESS TOKEN - CREATIVE TESTING SAAS")
    print("="*70)
    print()
    print("📋 Ce script teste si un User Access Token fourni par Pablo")
    print("   permet de récupérer les ad accounts et leurs données.")
    print()
    print("⚠️  IMPORTANT: Le token doit être envoyé en PRIVÉ (pas dans Slack)")
    print()

    # Demander le token
    if len(sys.argv) > 1:
        user_token = sys.argv[1].strip()
        print(f"✅ Token fourni via argument CLI")
    else:
        print("💡 Pour obtenir un User Access Token:")
        print("   1. Pablo va sur https://developers.facebook.com/tools/accesstoken/")
        print("   2. Sélectionne l'app 'Ads-Alchemy opt'")
        print("   3. Clique 'Generate Access Token'")
        print("   4. Copie le token et te l'envoie en PRIVÉ")
        print()
        user_token = input("Colle le User Access Token (ou ENTER pour quitter): ").strip()

    if not user_token:
        print("\n⏹️  Aucun token fourni. Arrêt.")
        print()
        print("💬 MESSAGE POUR PABLO:")
        print()
        print("   Salut Pablo,")
        print()
        print("   Pour qu'on puisse tester si l'authentification Facebook fonctionne")
        print("   correctement pour le SaaS, j'aurais besoin d'un User Access Token.")
        print()
        print("   Peux-tu:")
        print("   1. Aller sur https://developers.facebook.com/tools/accesstoken/")
        print("   2. Sélectionner l'app 'Ads-Alchemy opt'")
        print("   3. Cliquer 'Generate Access Token'")
        print("   4. Me l'envoyer en message privé (PAS dans un channel)")
        print()
        print("   Ça nous permettra de vérifier qu'on peut bien récupérer les ad")
        print("   accounts et leurs données, sans devoir te redemander d'infos plus tard.")
        print()
        print("   Merci!")
        print()
        sys.exit(0)

    # Lancer les tests
    user_data = test_token_validity(user_token)
    if not user_data:
        print("\n❌ Token invalide. Impossible de continuer.")
        sys.exit(1)

    permissions = test_token_permissions(user_token)

    accounts = test_ad_accounts(user_token)

    # Si on a des comptes, tester les insights sur le premier
    if accounts:
        first_account = accounts[0]['id']
        test_insights_sample(user_token, first_account)

    # Résumé final
    print_section("📊 RÉSUMÉ FINAL")

    if accounts and 'ads_read' in permissions:
        print("✅ SUCCÈS COMPLET!")
        print()
        print("   • Le token fonctionne")
        print("   • Les permissions sont accordées")
        print("   • On peut récupérer les ad accounts")
        print(f"   • {len(accounts)} compte(s) trouvé(s)")
        print()
        print("🎯 CONCLUSION:")
        print("   Les credentials fournis par Pablo sont SUFFISANTS pour")
        print("   implémenter le SaaS OAuth complet!")
        print()
        print("   ✅ On peut commencer à coder l'implémentation OAuth dans")
        print("      api/app/routers/auth.py avec confiance totale.")

    elif accounts and 'ads_read' not in permissions:
        print("⚠️  PROBLÈME PARTIEL")
        print()
        print("   • Le token fonctionne")
        print("   • On peut récupérer les ad accounts")
        print("   • MAIS: Permission 'ads_read' manquante")
        print()
        print("🎯 ACTION REQUISE:")
        print("   Pablo doit régénérer un token avec les permissions:")
        print("   • ads_read")
        print("   • business_management")

    else:
        print("❌ PROBLÈME DÉTECTÉ")
        print()
        print("   Impossible de récupérer les ad accounts.")
        print()
        print("🎯 CAUSES POSSIBLES:")
        print("   • Permissions insuffisantes")
        print("   • L'app n'a pas été approuvée pour ces permissions (App Review)")
        print("   • Le compte utilisateur n'a pas de comptes publicitaires")
        print()
        print("📋 PROCHAINE ÉTAPE:")
        print("   Partager ces résultats avec Pablo pour comprendre le blocage.")

    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏹️  Interrompu par l'utilisateur")
        sys.exit(0)
