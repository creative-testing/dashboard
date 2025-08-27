#!/usr/bin/env python3
"""
SCRIPT MASTER INTELLIGENT
Refresh toutes les périodes avec date de référence dynamique (toujours hier)
Solution définitive pour cohérence des données
"""
import os
import requests
import json
import sys
import subprocess
import shutil
from glob import glob
from dotenv import load_dotenv
from datetime import datetime, timedelta
from collections import defaultdict
import time as _time
from concurrent.futures import ThreadPoolExecutor, as_completed

load_dotenv()

def get_reference_date():
    """Date de référence intelligente : toujours hier (journée complète)"""
    yesterday = datetime.now() - timedelta(days=1)
    return yesterday.strftime('%Y-%m-%d')

def calculate_period_dates(period_days, reference_date):
    """Calcule fenêtre pour une période depuis date référence"""
    ref = datetime.strptime(reference_date, '%Y-%m-%d')
    end_date = ref
    start_date = ref - timedelta(days=period_days - 1)
    
    return start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')

def fetch_account_insights_optimized(account, token, since_date, until_date):
    """Fetch optimisé pour un compte"""
    account_id = account["id"]
    account_name = account.get("name", "Sans nom")
    
    try:
        url = f"https://graph.facebook.com/v23.0/{account_id}/insights"
        params = {
            "access_token": token,
            "level": "ad",
            "time_range": f'{{"since":"{since_date}","until":"{until_date}"}}',
            "time_increment": 1,
            "fields": "ad_id,ad_name,campaign_name,adset_name,impressions,spend,clicks,ctr,cpm,reach,frequency,actions,action_values,cost_per_action_type",
            "filtering": '[{"field":"impressions","operator":"GREATER_THAN","value":"0"}]',
            "limit": 1000
        }
        
        # Pagination complète
        all_ads = []
        current_url = url
        page = 0
        
        backoff = 1
        while current_url and page < 30:  # Limite sécurité
            try:
                if page == 0:
                    response = requests.get(current_url, params=params)
                else:
                    response = requests.get(current_url)
                try:
                    data = response.json()
                except Exception:
                    data = {}
                # rate limit handling
                if response.status_code != 200:
                    msg = str(data)
                    if '#80004' in msg or 'too many calls' in msg.lower() or response.status_code == 429:
                        import time, random
                        delay = min(30, backoff) + random.random()
                        time.sleep(delay)
                        backoff *= 2
                        continue
                    break
            except Exception:
                break
            
            if "data" in data:
                ads = data["data"]
                
                # Enrichir avec account info
                for ad in ads:
                    ad['account_name'] = account_name
                    ad['account_id'] = account_id
                
                all_ads.extend(ads)
                
                # Pagination
                if "paging" in data and "next" in data["paging"]:
                    current_url = data["paging"]["next"]
                    page += 1
                else:
                    break
            else:
                break
        
        return all_ads
        
    except Exception as e:
        return []

def fetch_creatives_parallel(ad_ids, token):
    """Fetch creatives en parallèle"""
    
    def fetch_batch(ad_ids_batch):
        batch_requests = [
            {"method": "GET", "relative_url": f"{ad_id}?fields=creative{{video_id,image_url,instagram_permalink_url}}"}
            for ad_id in ad_ids_batch
        ]
        
        try:
            response = requests.post("https://graph.facebook.com/v23.0/", data={
                "access_token": token,
                "batch": json.dumps(batch_requests)
            })
            
            results = response.json()
            creatives = {}
            
            # ✅ Fix: Vérifier que results est une liste
            if not isinstance(results, list):
                print(f"⚠️  Batch response not a list: {type(results)}")
                return {}
            
            for result in results:
                # ✅ Fix: Vérifier que result est un dict  
                if not isinstance(result, dict):
                    continue
                    
                if result.get("code") == 200:
                    body = json.loads(result["body"])
                    ad_id = body.get("id")
                    if ad_id and "creative" in body:
                        creatives[ad_id] = body["creative"]
            
            return creatives
            
        except:
            return {}
    
    # Diviser en batches
    batch_size = 100
    batches = [ad_ids[i:i+batch_size] for i in range(0, len(ad_ids), batch_size)]
    
    all_creatives = {}
    
    with ThreadPoolExecutor(max_workers=30) as executor:  # Agressif pour M1 Pro
        futures = [executor.submit(fetch_batch, batch) for batch in batches]
        
        for future in as_completed(futures):
            batch_creatives = future.result()
            all_creatives.update(batch_creatives)
    
    return all_creatives

def master_refresh():
    """Fonction master : refresh tout avec cohérence"""
    
    token = os.getenv("FACEBOOK_ACCESS_TOKEN")
    if not token:
        raise SystemExit("FACEBOOK_ACCESS_TOKEN not set. Define it in .env")
    reference_date = get_reference_date()
    
    print("🚀 MASTER REFRESH - SOLUTION INTELLIGENTE")
    print("=" * 70)
    print(f"📅 Date référence (hier): {reference_date}")
    print(f"🕐 Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"💻 Optimisé pour MacBook M1 Pro")
    
    start_master = _time.time()
    
    # 1. Comptes (une seule fois)
    print(f"\n📊 Récupération comptes...")
    # Adaccounts pagination
    accounts = []
    url = "https://graph.facebook.com/v23.0/me/adaccounts"
    params = {
        "access_token": token,
        "fields": "id,name,account_status",
        "limit": 100,
    }
    retry = 0
    while url:
        resp = requests.get(url, params=params)
        try:
            data = resp.json()
        except Exception:
            data = {}
        if resp.status_code != 200:
            print(f"⚠️ adaccounts HTTP {resp.status_code}: {str(data)[:200]}")
            # simple backoff on rate limits
            if data and isinstance(data, dict) and 'error' in data:
                msg = str(data['error'])
                if '#80004' in msg or 'too many calls' in msg.lower():
                    import time
                    delay = min(30, 2 ** retry)
                    print(f"⏳ Rate limit: attente {delay}s et nouvelle tentative...")
                    time.sleep(delay)
                    retry += 1
                    if retry <= 3:
                        continue
            break
        accounts.extend(data.get("data", []) or [])
        # follow next
        url = data.get("paging", {}).get("next")
        params = None  # next already has params

    active_accounts = [acc for acc in accounts if (acc.get("account_status") == 1 or acc.get("account_status") == "1")]
    
    # Debug (optional)
    if os.getenv('DEBUG_REFRESH'):
        print(f"👀 Adaccounts renvoyés: {len(accounts)}")
        if accounts[:3]:
            try:
                sample = [{k: a.get(k) for k in ("id","name","account_status")} for a in accounts[:3]]
                print(f"   échantillon: {sample}")
            except Exception:
                pass

    # Fallback: explicit account IDs via env if nothing returned
    if not active_accounts:
        env_ids = os.getenv("META_ACCOUNT_IDS", "").strip()
        if env_ids:
            print("⚠️ Aucun compte actif listé via /me/adaccounts, utilisation de META_ACCOUNT_IDS")
            active_accounts = [{"id": acc.strip(), "name": acc.strip(), "account_status": 1} for acc in env_ids.split(',') if acc.strip()]
    print(f"✅ {len(active_accounts)} comptes actifs")
    
    # 2. Mode baseline journalier 90j + agrégations locales (moins d'appels)
    results_summary = {}
    print("\n🧱 Baseline journalière 90j (time_increment=1)...")
    start_baseline = _time.time()

    # Fenêtre 90 jours
    since_date_90, until_date_90 = calculate_period_dates(90, reference_date)

    # Collecte journalière pour chaque compte
    daily_rows = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futs = [
            executor.submit(fetch_account_insights_optimized, acc, token, since_date_90, until_date_90)
            for acc in active_accounts
        ]
        for fut in as_completed(futs):
            daily_rows.extend(fut.result())

    # Taguer chaque ligne avec une date si non présente (Meta renvoie souvent date_start/date_stop ou des buckets)
    for r in daily_rows:
        # si disponible, garder la granularité/jour (Meta inclut souvent date_start/date_stop par bucket)
        r['date'] = r.get('date_start') or r.get('date') or ''

    baseline = {
        'metadata': {
            'timestamp': datetime.now().isoformat(),
            'reference_date': reference_date,
            'date_range': f"{since_date_90} to {until_date_90}",
            'method': 'baseline_90d_daily',
            'total_rows': len(daily_rows)
        },
        'daily_ads': daily_rows
    }
    os.makedirs('data/current', exist_ok=True)
    with open('data/current/baseline_90d_daily.json', 'w', encoding='utf-8') as f:
        json.dump(baseline, f, indent=2, ensure_ascii=False)
    print(f"   ✅ Baseline 90j: {len(daily_rows)} lignes en {_time.time()-start_baseline:.1f}s")

    # Agrégations locales vers 3/7/14/30/90
    print("\n🧮 Agrégation locale vers périodes...")
    # Import local pour éviter problèmes de chemins
    sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
    from utils.aggregate_periods import aggregate_from_baseline  # type: ignore
    periods = [3,7,14,30,90]
    for period in periods:
        out = aggregate_from_baseline('data/current/baseline_90d_daily.json', period_days=period, reference_date=reference_date)
        with open(f'data/current/hybrid_data_{period}d.json', 'w', encoding='utf-8') as f:
            json.dump(out, f, indent=2, ensure_ascii=False)
        results_summary[period] = {
            'ads': out['metadata'].get('total_ads', 0),
            'spend': sum(a.get('spend',0) for a in out.get('ads',[])),
            'time': 0.0,
        }
        print(f"   ✅ {period}j: {results_summary[period]['ads']} ads agrégées")
    
    # Résumé final
    master_time = _time.time() - start_master
    
    print(f"\n" + "=" * 70)
    print(f"🎉 MASTER REFRESH TERMINÉ")
    print(f"⚡ Temps total: {master_time/60:.1f} minutes")
    print(f"📅 Toutes périodes cohérentes depuis: {reference_date}")
    
    print(f"\n📊 RÉSUMÉ PAR PÉRIODE:")
    for period, stats in results_summary.items():
        print(f"  {period:2}j: {stats['ads']:4} ads, ${stats['spend']:>8,.0f} MXN, {stats['time']:4.1f}s")
    
    # Créer fichier de config pour l'interface
    config_output = {
        "last_update": datetime.now().isoformat(),
        "reference_date": reference_date,
        "periods_available": list(results_summary.keys()),
        "total_execution_time": master_time
    }
    
    with open('data/current/refresh_config.json', 'w') as f:
        json.dump(config_output, f, indent=2)
    
    print(f"\n💾 Config sauvegardée pour interface")

    # Si aucune annonce n'a été récupérée, éviter d'écraser des fichiers valides
    total_ads_all = sum(v.get('ads', 0) for v in results_summary.values())

    # 3. Récupération semaine précédente (pour comparaison)
    try:
        print("\n📆 Refresh semaine précédente (comparaison)...")
        subprocess.run([sys.executable, 'scripts/production/fetch_prev_week.py'], check=True)
        print("✅ Semaine précédente OK")
    except Exception as e:
        print(f"⚠️ Impossible de rafraîchir la semaine précédente: {e}")

    # 4. Enrichissement media_url (intégré)
    try:
        print("\n🎬 Enrichissement media_url (intégré) sur data/current...")
        # Import paresseux pour éviter problèmes de path
        sys.path.append(os.path.join(os.path.dirname(__file__), '..'))  # add scripts/
        from utils.enrich_media import enrich_media_urls_union  # type: ignore
        stats = enrich_media_urls_union(base_dir='data/current', periods=[3,7,14,30,90], max_workers=10, only_missing=True)
        print("✅ Enrichissement media_url OK:")
        for k,v in stats.items():
            if k.startswith('_'): continue
            print(f"   {k}d: {v.get('with_media',0)}/{v.get('total',0)}")
    except Exception as e:
        print(f"⚠️ Impossible d'enrichir media_url: {e}")

    # 5. Miroir de compatibilité vers la racine (source de vérité = data/current)
    mirror_flag = os.getenv('MIRROR_TO_ROOT', 'false').lower() in ('1','true','yes','on')
    if total_ads_all > 0 and mirror_flag:
        try:
            print("\n🔁 Miroir des fichiers vers la racine (compatibilité)...")
            files = [
                *(f"data/current/hybrid_data_{p}d.json" for p in [3, 7, 14, 30, 90]),
                "data/current/hybrid_data_prev_week.json",
                "data/current/refresh_config.json",
            ]
            # Petcare (facultatif)
            petcare_json = 'data/current/petcare_parsed_analysis.json'
            if os.path.exists(petcare_json):
                files.append(petcare_json)

            for src in files:
                if os.path.exists(src):
                    dst = os.path.basename(src)
                    shutil.copy2(src, dst)
            print("✅ Miroir racine OK")
        except Exception as e:
            print(f"⚠️ Miroir racine échoué: {e}")
    else:
        if total_ads_all == 0:
            print("⚠️ 0 annonces récupérées: pas de miroir vers la racine pour protéger les fichiers existants.")
        elif not mirror_flag:
            print("ℹ️ MIRROR_TO_ROOT désactivé: pas de copie des JSON vers la racine.")

    return results_summary

if __name__ == "__main__":
    print("🤖 SCRIPT MASTER - REFRESH INTELLIGENT")
    print("🎯 Toutes périodes cohérentes depuis date référence dynamique")
    print("⚡ Optimisé MacBook M1 Pro - Parallélisation aggressive") 
    print()
    
    results = master_refresh()
    
    if results:
        print(f"\n✅ SUCCESS! Toutes données cohérentes et prêtes")
        print(f"🎯 Interface peut maintenant afficher dates précises")
        print(f"🚀 Dashboard Pablo ready!")
