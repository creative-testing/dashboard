#!/usr/bin/env python3
"""
Script de récupération des données Facebook Ads via MCP
Utilise le serveur MCP local pour accéder aux 64 comptes
"""
import os
import json
import subprocess
from datetime import datetime, timedelta
from collections import defaultdict
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

load_dotenv()

def get_reference_date():
    """Date de référence : toujours hier (journée complète)"""
    yesterday = datetime.now() - timedelta(days=1)
    return yesterday.strftime('%Y-%m-%d')

def calculate_period_dates(period_days, reference_date):
    """Calcule fenêtre pour une période depuis date référence"""
    ref = datetime.strptime(reference_date, '%Y-%m-%d')
    end_date = ref
    start_date = ref - timedelta(days=period_days - 1)
    return start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')

def call_mcp_tool(tool_name, params):
    """Appel générique à un tool MCP via subprocess"""
    try:
        # Préparer la commande pour appeler le serveur MCP
        cmd = [
            'python', '-c',
            f"""
import os
import json
from dotenv import load_dotenv
load_dotenv()

# Configurer le token
token = os.getenv('FACEBOOK_ACCESS_TOKEN')
os.environ['META_ACCESS_TOKEN'] = token

# Importer et utiliser le module MCP
from meta_ads_mcp import {tool_name}

params = {json.dumps(params)}
result = {tool_name}(**params)
print(json.dumps(result))
"""
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.stdout:
            return json.loads(result.stdout)
        return None
    except Exception as e:
        print(f"Erreur MCP {tool_name}: {e}")
        return None

def fetch_accounts_via_mcp():
    """Récupère la liste des comptes via MCP"""
    result = call_mcp_tool('get_ad_accounts', {'limit': 200})
    if result and 'data' in result:
        return result['data']
    return []

def fetch_account_campaigns(account_id):
    """Récupère les campagnes d'un compte"""
    result = call_mcp_tool('get_campaigns', {
        'account_id': account_id,
        'limit': 100
    })
    if result and 'data' in result:
        return result['data']
    return []

def fetch_insights_for_account(account_id, since_date, until_date):
    """Récupère les insights pour un compte sur une période"""
    try:
        result = call_mcp_tool('get_insights', {
            'object_id': account_id,
            'time_range': {
                'since': since_date,
                'until': until_date
            },
            'level': 'ad',
            'breakdown': ''
        })
        
        if result and 'data' in result:
            return result['data']
    except Exception as e:
        print(f"Erreur insights {account_id}: {e}")
    return []

def enrich_with_creative_data(ads_data):
    """Enrichit les données avec les URLs des creatives"""
    enriched = []
    
    for ad in ads_data:
        ad_id = ad.get('ad_id')
        if not ad_id:
            enriched.append(ad)
            continue
            
        # Récupérer les données créatives
        creative_result = call_mcp_tool('get_ad_creatives', {'ad_id': ad_id})
        
        if creative_result:
            ad['video_id'] = creative_result.get('video_id')
            ad['image_url'] = creative_result.get('image_url') or creative_result.get('thumbnail_url')
            ad['instagram_permalink_url'] = creative_result.get('instagram_permalink_url')
        
        enriched.append(ad)
    
    return enriched

def process_insights_data(raw_data, account_name, account_id):
    """Traite les données insights pour le format attendu"""
    processed = []
    
    for item in raw_data:
        # Extraire les métriques clés
        spend = float(item.get('spend', 0))
        impressions = int(item.get('impressions', 0))
        clicks = int(item.get('clicks', 0))
        
        # Calculer les conversions et valeurs
        actions = item.get('actions', [])
        conversions = 0
        conversion_value = 0
        
        for action in actions:
            if action.get('action_type') in ['purchase', 'omni_purchase']:
                conversions += int(action.get('value', 0))
        
        action_values = item.get('action_values', [])
        for value in action_values:
            if value.get('action_type') in ['purchase', 'omni_purchase']:
                conversion_value += float(value.get('value', 0))
        
        # Calculer ROAS et CPA
        roas = conversion_value / spend if spend > 0 else 0
        cpa = spend / conversions if conversions > 0 else 0
        
        processed_ad = {
            'ad_id': item.get('ad_id'),
            'ad_name': item.get('ad_name'),
            'campaign_name': item.get('campaign_name'),
            'adset_name': item.get('adset_name'),
            'account_name': account_name,
            'account_id': account_id,
            'date': item.get('date_start'),
            'impressions': impressions,
            'spend': spend,
            'clicks': clicks,
            'ctr': float(item.get('ctr', 0)),
            'cpm': float(item.get('cpm', 0)),
            'reach': int(item.get('reach', 0)),
            'frequency': float(item.get('frequency', 0)),
            'conversions': conversions,
            'conversion_value': conversion_value,
            'roas': roas,
            'cpa': cpa
        }
        
        processed.append(processed_ad)
    
    return processed

def aggregate_by_period(daily_data, period_days, reference_date):
    """Agrège les données journalières pour une période"""
    ref = datetime.strptime(reference_date, '%Y-%m-%d')
    start = ref - timedelta(days=period_days - 1)
    
    # Filtrer les données dans la période
    filtered = []
    for ad in daily_data:
        if ad.get('date'):
            ad_date = datetime.strptime(ad['date'], '%Y-%m-%d')
            if start <= ad_date <= ref:
                filtered.append(ad)
    
    # Agréger par ad_id
    aggregated = defaultdict(lambda: {
        'impressions': 0,
        'spend': 0,
        'clicks': 0,
        'reach': 0,
        'conversions': 0,
        'conversion_value': 0,
        'dates': []
    })
    
    for ad in filtered:
        ad_id = ad['ad_id']
        aggregated[ad_id]['impressions'] += ad['impressions']
        aggregated[ad_id]['spend'] += ad['spend']
        aggregated[ad_id]['clicks'] += ad['clicks']
        aggregated[ad_id]['reach'] = max(aggregated[ad_id]['reach'], ad['reach'])
        aggregated[ad_id]['conversions'] += ad['conversions']
        aggregated[ad_id]['conversion_value'] += ad['conversion_value']
        aggregated[ad_id]['dates'].append(ad['date'])
        
        # Conserver les infos de base
        if 'ad_name' not in aggregated[ad_id]:
            aggregated[ad_id].update({
                'ad_id': ad_id,
                'ad_name': ad['ad_name'],
                'campaign_name': ad['campaign_name'],
                'adset_name': ad['adset_name'],
                'account_name': ad['account_name'],
                'account_id': ad['account_id']
            })
    
    # Calculer les métriques dérivées
    result = []
    for ad_id, data in aggregated.items():
        spend = data['spend']
        impressions = data['impressions']
        clicks = data['clicks']
        conversions = data['conversions']
        
        data['ctr'] = (clicks / impressions * 100) if impressions > 0 else 0
        data['cpm'] = (spend / impressions * 1000) if impressions > 0 else 0
        data['frequency'] = impressions / data['reach'] if data['reach'] > 0 else 0
        data['roas'] = data['conversion_value'] / spend if spend > 0 else 0
        data['cpa'] = spend / conversions if conversions > 0 else 0
        data['active_days'] = len(set(data['dates']))
        
        del data['dates']
        result.append(data)
    
    return result

def main():
    """Fonction principale"""
    print("🚀 MCP REFRESH - Récupération via Meta Ads MCP")
    print("=" * 70)
    
    reference_date = get_reference_date()
    print(f"📅 Date référence (hier): {reference_date}")
    print(f"🕐 Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    start_time = time.time()
    
    # 1. Récupérer la liste des comptes
    print("\n📊 Récupération des comptes via MCP...")
    accounts = fetch_accounts_via_mcp()
    
    if not accounts:
        print("❌ Aucun compte trouvé via MCP")
        print("💡 Vérifiez que le serveur MCP est lancé et le token configuré")
        return
    
    print(f"✅ {len(accounts)} comptes trouvés")
    
    # Filtrer les comptes actifs
    active_accounts = [acc for acc in accounts if acc.get('account_status') in [1, '1', 'ACTIVE']]
    print(f"✅ {len(active_accounts)} comptes actifs")
    
    # Sauvegarder l'index des comptes
    os.makedirs('data/current', exist_ok=True)
    accounts_index = {
        'timestamp': datetime.now().isoformat(),
        'total': len(accounts),
        'active_total': len(active_accounts),
        'accounts': accounts,
        'active_accounts': active_accounts
    }
    with open('data/current/accounts_index.json', 'w', encoding='utf-8') as f:
        json.dump(accounts_index, f, indent=2, ensure_ascii=False)
    
    # 2. Collecter les données pour chaque compte (90 jours)
    print("\n🔄 Collecte des données 90 jours...")
    since_date, until_date = calculate_period_dates(90, reference_date)
    
    all_daily_data = []
    accounts_with_data = 0
    
    for account in active_accounts[:10]:  # Limiter pour les tests
        account_id = account['id']
        account_name = account.get('name', 'Unknown')
        
        print(f"  📍 {account_name} ({account_id})...", end='')
        
        # Vérifier d'abord si le compte a des campagnes
        campaigns = fetch_account_campaigns(account_id)
        if not campaigns:
            print(" (0 campagnes)")
            continue
        
        # Récupérer les insights
        insights = fetch_insights_for_account(account_id, since_date, until_date)
        
        if insights:
            processed = process_insights_data(insights, account_name, account_id)
            all_daily_data.extend(processed)
            accounts_with_data += 1
            print(f" ✓ {len(processed)} ads")
        else:
            print(" (pas de données)")
    
    print(f"\n✅ Données collectées: {len(all_daily_data)} ads de {accounts_with_data} comptes")
    
    # 3. Enrichir avec les données créatives (media URLs)
    if all_daily_data:
        print("\n🎬 Enrichissement des media URLs...")
        all_daily_data = enrich_with_creative_data(all_daily_data[:50])  # Limiter pour tests
        print("✅ Enrichissement terminé")
    
    # 4. Sauvegarder les données baseline
    baseline = {
        'metadata': {
            'timestamp': datetime.now().isoformat(),
            'reference_date': reference_date,
            'date_range': f"{since_date} to {until_date}",
            'method': 'mcp_baseline_90d',
            'total_rows': len(all_daily_data),
            'accounts_with_data': accounts_with_data
        },
        'daily_ads': all_daily_data
    }
    
    with open('data/current/baseline_90d_daily.json', 'w', encoding='utf-8') as f:
        json.dump(baseline, f, indent=2, ensure_ascii=False)
    
    # 5. Créer les agrégations par période
    print("\n📊 Génération des périodes...")
    periods = [3, 7, 14, 30, 90]
    
    for period in periods:
        aggregated = aggregate_by_period(all_daily_data, period, reference_date)
        
        output = {
            'metadata': {
                'timestamp': datetime.now().isoformat(),
                'reference_date': reference_date,
                'period_days': period,
                'total_ads': len(aggregated),
                'total_spend': sum(ad['spend'] for ad in aggregated),
                'total_conversion_value': sum(ad['conversion_value'] for ad in aggregated)
            },
            'ads': aggregated
        }
        
        with open(f'data/current/hybrid_data_{period}d.json', 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        print(f"  ✅ {period}j: {len(aggregated)} ads, ${output['metadata']['total_spend']:,.0f}")
    
    # 6. Générer la semaine précédente pour comparaison
    prev_ref = (datetime.strptime(reference_date, '%Y-%m-%d') - timedelta(days=7)).strftime('%Y-%m-%d')
    prev_week = aggregate_by_period(all_daily_data, 7, prev_ref)
    
    prev_output = {
        'metadata': {
            'timestamp': datetime.now().isoformat(),
            'reference_date': prev_ref,
            'period_days': 7,
            'total_ads': len(prev_week),
            'total_spend': sum(ad['spend'] for ad in prev_week)
        },
        'ads': prev_week
    }
    
    with open('data/current/hybrid_data_prev_week.json', 'w', encoding='utf-8') as f:
        json.dump(prev_output, f, indent=2, ensure_ascii=False)
    
    # 7. Créer le fichier de config
    config_output = {
        "last_update": datetime.now().isoformat(),
        "reference_date": reference_date,
        "periods_available": periods,
        "total_execution_time": time.time() - start_time,
        "accounts_processed": accounts_with_data,
        "total_ads": len(all_daily_data)
    }
    
    with open('data/current/refresh_config.json', 'w', encoding='utf-8') as f:
        json.dump(config_output, f, indent=2)
    
    print(f"\n🎉 MCP REFRESH TERMINÉ")
    print(f"⏱️  Temps total: {(time.time() - start_time)/60:.1f} minutes")
    print(f"📊 Total: {len(all_daily_data)} ads de {accounts_with_data} comptes")

if __name__ == '__main__':
    main()