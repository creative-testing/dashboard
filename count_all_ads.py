#!/usr/bin/env python3
"""
Script pour compter TOUTES les annonces sur différentes périodes
"""
import requests
from config import MetaConfig
from dotenv import load_dotenv
import os

load_dotenv()

def count_ads_by_period():
    token = os.getenv("FB_TOKEN")
    account_id = "act_297112083495970"
    
    print("📊 COMPTAGE DE TOUTES LES ANNONCES PAR PÉRIODE")
    print("=" * 60)
    
    periods = [
        ("today", "Aujourd'hui"),
        ("yesterday", "Hier"),
        ("last_7d", "7 derniers jours"),
        ("last_14d", "14 derniers jours"),
        ("last_30d", "30 derniers jours"),
        ("last_90d", "90 derniers jours"),
        ("maximum", "Maximum (toute la durée de vie)"),
    ]
    
    for period_key, period_name in periods:
        try:
            # Première requête pour avoir le total
            url = f"https://graph.facebook.com/v23.0/{account_id}/insights"
            params = {
                "access_token": token,
                "level": "ad",
                "date_preset": period_key,
                "fields": "ad_id,spend,impressions",
                "limit": 500,  # Maximum par page
            }
            
            response = requests.get(url, params=params)
            data = response.json()
            
            if "error" in data:
                print(f"\n❌ {period_name}: Erreur - {data['error'].get('message', 'Unknown')}")
                continue
            
            # Compter les résultats
            first_batch = len(data.get("data", []))
            
            # Calculer le total approximatif basé sur la pagination
            total_count = first_batch
            total_spend = sum(float(ad.get("spend", 0)) for ad in data.get("data", []))
            total_impressions = sum(int(ad.get("impressions", 0)) for ad in data.get("data", []))
            
            # S'il y a plus de pages, estimer le total
            if "paging" in data and "next" in data["paging"]:
                # Il y a plus de données
                print(f"\n📅 {period_name} ({period_key}):")
                print(f"  Premier batch: {first_batch} annonces")
                print(f"  ⚠️ Il y a PLUS de données (pagination détectée)")
                
                # Essayer de compter toutes les pages (limité pour éviter timeout)
                next_url = data["paging"]["next"]
                page_count = 1
                max_pages = 5  # Limiter pour éviter timeout
                
                while next_url and page_count < max_pages:
                    try:
                        response = requests.get(next_url)
                        data = response.json()
                        batch_size = len(data.get("data", []))
                        total_count += batch_size
                        total_spend += sum(float(ad.get("spend", 0)) for ad in data.get("data", []))
                        total_impressions += sum(int(ad.get("impressions", 0)) for ad in data.get("data", []))
                        
                        if "paging" in data and "next" in data["paging"]:
                            next_url = data["paging"]["next"]
                            page_count += 1
                        else:
                            next_url = None
                            
                    except:
                        break
                
                if page_count >= max_pages:
                    print(f"  📊 Minimum {total_count}+ annonces (arrêté après {page_count} pages)")
                else:
                    print(f"  📊 Total exact: {total_count} annonces")
            else:
                print(f"\n📅 {period_name} ({period_key}):")
                print(f"  📊 Total: {total_count} annonces")
            
            # Afficher les stats
            print(f"  💰 Dépense totale: ${total_spend:,.2f}")
            print(f"  👁️ Impressions totales: {total_impressions:,}")
            
            # Pour les annonces actives uniquement
            if period_key == "last_7d":
                # Essayer avec filtre sur status
                params_active = params.copy()
                params_active["filtering"] = '[{"field":"spend","operator":"GREATER_THAN","value":"0"}]'
                
                response_active = requests.get(url, params=params_active)
                if response_active.status_code == 200:
                    data_active = response_active.json()
                    active_count = len(data_active.get("data", []))
                    print(f"  ✅ Annonces avec dépenses > 0: {active_count}")
            
        except Exception as e:
            print(f"\n❌ {period_name}: Erreur - {str(e)}")
    
    # Test spécifique : compter TOUTES les annonces du compte
    print("\n" + "=" * 60)
    print("🔍 TEST: Récupération de TOUTES les annonces (via /ads endpoint)")
    
    try:
        url = f"https://graph.facebook.com/v23.0/{account_id}/ads"
        params = {
            "access_token": token,
            "fields": "id,name,effective_status,created_time",
            "limit": 500
        }
        
        response = requests.get(url, params=params)
        data = response.json()
        
        if "data" in data:
            ads = data["data"]
            
            # Compter par statut
            status_count = {}
            for ad in ads:
                status = ad.get("effective_status", "UNKNOWN")
                status_count[status] = status_count.get(status, 0) + 1
            
            print(f"\n📌 Total d'annonces dans le compte: {len(ads)}")
            print("Répartition par statut:")
            for status, count in sorted(status_count.items()):
                print(f"  - {status}: {count}")
            
            # S'il y a pagination
            if "paging" in data and "next" in data["paging"]:
                print("  ⚠️ Il y a ENCORE PLUS d'annonces (pagination)")
    
    except Exception as e:
        print(f"Erreur: {e}")

if __name__ == "__main__":
    count_ads_by_period()