#!/usr/bin/env python3
"""
Vérification rapide de la nomenclature mise par Martin
Récupère juste les noms des annonces actives pour analyser le pattern
"""
import os
import requests
from dotenv import load_dotenv
from collections import defaultdict
import re

load_dotenv()

def check_nomenclature():
    """Vérification rapide de la nomenclature de Martin"""
    
    token = os.getenv("FB_TOKEN")
    
    print("🔍 VÉRIFICATION NOMENCLATURE DE MARTIN")
    print("=" * 60)
    print("🎯 Objectif: Comprendre le format des noms d'annonces")
    
    # Récupérer quelques comptes actifs
    accounts_url = "https://graph.facebook.com/v23.0/me/adaccounts"
    response = requests.get(accounts_url, params={
        "access_token": token,
        "fields": "id,name,account_status",
        "limit": 20  # Just les premiers pour test rapide
    })
    
    accounts = response.json().get("data", [])
    active_accounts = [acc for acc in accounts if acc.get("account_status") == 1][:10]  # Top 10
    
    print(f"📊 Test sur {len(active_accounts)} comptes...")
    
    # Récupérer annonces actives récentes
    all_ad_names = []
    
    for account in active_accounts:
        account_id = account["id"]
        account_name = account.get("name", "Unknown")
        
        print(f"   {account_name[:30]:30}...", end="", flush=True)
        
        try:
            # Juste les annonces actives des 3 derniers jours
            ads_url = f"https://graph.facebook.com/v23.0/{account_id}/ads"
            params = {
                "access_token": token,
                "fields": "id,name,effective_status,created_time",
                "effective_status": '["ACTIVE"]',
                "limit": 50
            }
            
            response = requests.get(ads_url, params=params)
            data = response.json()
            
            if "data" in data:
                ads = data["data"]
                for ad in ads:
                    ad_name = ad.get("name", "")
                    if ad_name:
                        all_ad_names.append({
                            "name": ad_name,
                            "account": account_name,
                            "status": ad.get("effective_status"),
                            "created": ad.get("created_time", "")[:10]  # Just date
                        })
                
                print(f" ✅ {len(ads)} ads actives")
            else:
                print(" ❌ No data")
                
        except Exception as e:
            print(f" ❌ {e}")
    
    print(f"\n✅ {len(all_ad_names)} noms d'annonces collectés")
    
    # Analyse des patterns
    print(f"\n🔍 ANALYSE DES PATTERNS DE NOMENCLATURE")
    print("=" * 60)
    
    # Échantillon des noms
    print(f"\n📋 ÉCHANTILLON DES NOMS (20 premiers):")
    for i, ad in enumerate(all_ad_names[:20], 1):
        created = ad['created'] if ad['created'] else 'N/A'
        print(f"  {i:2}. {ad['name'][:70]:70} ({ad['account'][:15]}, {created})")
    
    # Recherche de patterns
    print(f"\n🔍 RECHERCHE DE PATTERNS:")
    
    patterns = {
        "pipe_separator": 0,
        "slash_separator": 0, 
        "dash_separator": 0,
        "underscore_separator": 0,
        "with_angle": 0,
        "with_formato": 0,
        "with_creador": 0
    }
    
    angle_keywords = ["inflamacion", "energia", "digestion", "proteina", "antienvejecimiento", "belleza"]
    format_keywords = ["video", "image", "imagen", "carousel", "carrusel"]
    
    for ad in all_ad_names:
        name_lower = ad['name'].lower()
        
        # Séparateurs
        if "|" in ad['name']:
            patterns["pipe_separator"] += 1
        if "/" in ad['name']:
            patterns["slash_separator"] += 1
        if "-" in ad['name']:
            patterns["dash_separator"] += 1
        if "_" in ad['name']:
            patterns["underscore_separator"] += 1
        
        # Angles
        for angle in angle_keywords:
            if angle in name_lower:
                patterns["with_angle"] += 1
                break
        
        # Formats
        for fmt in format_keywords:
            if fmt in name_lower:
                patterns["with_formato"] += 1
                break
        
        # Créateurs (chercher prénoms + âges)
        if re.search(r'\b(carlos|ana|luis|maria|miguel|sofia)\b', name_lower):
            patterns["with_creador"] += 1
    
    print(f"\n📈 STATISTIQUES:")
    total = len(all_ad_names)
    for pattern, count in patterns.items():
        percentage = (count / total * 100) if total > 0 else 0
        print(f"  • {pattern:20}: {count:4} / {total} ({percentage:5.1f}%)")
    
    # Détection du format principal
    print(f"\n🎯 CONCLUSIONS:")
    
    if patterns["pipe_separator"] > total * 0.7:
        print("  ✅ NOMENCLATURE STRUCTURÉE avec séparateur |")
        print("  → Format probable: FORMATO|ANGLE|HOOK|CREADOR|VERSION")
    elif patterns["dash_separator"] > total * 0.5:
        print("  ✅ NOMENCLATURE avec tirets -")
    else:
        print("  ⚠️  Nomenclature mixte ou en cours")
    
    if patterns["with_angle"] > total * 0.5:
        print("  ✅ ANGLES détectés dans les noms")
    
    if patterns["with_creador"] > total * 0.3:
        print("  ✅ CRÉATEURS détectés dans les noms")
    
    print(f"\n💡 RECOMMANDATIONS:")
    if patterns["pipe_separator"] > total * 0.5:
        print("  → Créer parser avec split('|')")
        print("  → Débloquer analyses par angle/creador") 
        print("  → Remplacer section Preview par vraies données")
    else:
        print("  → Attendre fin de nomenclature ou créer parser adaptatif")
    
    return all_ad_names[:10]  # Retourner échantillon pour debug

if __name__ == "__main__":
    print("🕵️ Inspection de la nomenclature de Martin")
    print("🕐 Annonces modifiées récemment")
    
    samples = check_nomenclature()
    
    if samples:
        print(f"\n✨ Échantillon récupéré pour analyse !")