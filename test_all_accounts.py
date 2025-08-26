#!/usr/bin/env python3
"""
Test avec le SDK Facebook Business pour voir TOUS les comptes
(Comme dans le projet agente_creativo_ia)
"""
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.user import User
from facebook_business.adobjects.adaccount import AdAccount
import os
from dotenv import load_dotenv

load_dotenv()

def test_all_accounts_with_sdk():
    """Test avec le SDK Facebook Business comme dans l'autre projet"""
    
    token = os.getenv("FB_TOKEN")  # UN SEUL TOKEN !
    
    print("🔍 TEST AVEC LE SDK FACEBOOK BUSINESS")
    print("=" * 60)
    
    try:
        # Initialiser l'API avec le token
        api = FacebookAdsApi.init(access_token=token)
        
        # Créer un objet User pour 'me'
        me = User(fbid='me', api=api)
        
        # Récupérer TOUS les comptes publicitaires
        print("\n📊 Récupération des comptes publicitaires...")
        
        ad_accounts = list(me.get_ad_accounts(fields=[
            AdAccount.Field.id,
            AdAccount.Field.name,
            AdAccount.Field.account_id,
            AdAccount.Field.account_status,
            AdAccount.Field.currency,
            AdAccount.Field.timezone_name
        ]))
        
        print(f"\n✅ TOTAL: {len(ad_accounts)} comptes trouvés!")
        
        # Afficher les détails
        active_count = 0
        inactive_count = 0
        
        print("\nListe des comptes:")
        print("-" * 60)
        
        for i, account in enumerate(ad_accounts, 1):
            status = account[AdAccount.Field.account_status]
            is_active = status == 1
            
            if is_active:
                active_count += 1
                status_text = "✅ ACTIF"
            else:
                inactive_count += 1
                status_text = "❌ INACTIF"
            
            print(f"\n{i}. {account[AdAccount.Field.name]}")
            print(f"   ID: {account[AdAccount.Field.id]}")
            print(f"   Status: {status_text}")
            print(f"   Devise: {account.get(AdAccount.Field.currency, 'N/A')}")
            
            # Limiter l'affichage
            if i >= 10 and len(ad_accounts) > 10:
                print(f"\n... et {len(ad_accounts) - 10} autres comptes")
                break
        
        print(f"\n📊 RÉSUMÉ:")
        print(f"  • Total: {len(ad_accounts)} comptes")
        print(f"  • Actifs: {active_count}")
        print(f"  • Inactifs: {inactive_count}")
        
        # Tester si on peut paginer pour en avoir plus
        if hasattr(ad_accounts, '_has_next'):
            print(f"\n⚠️ Il pourrait y avoir encore plus de comptes (pagination)")
        
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_all_accounts_with_sdk()