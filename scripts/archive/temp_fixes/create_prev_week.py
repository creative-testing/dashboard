#!/usr/bin/env python3
"""
Créer prev_week_data.json à partir du baseline existant
"""
import json
from datetime import datetime, timedelta

# Charger le baseline
with open('data/current/baseline_90d_daily.json', 'r') as f:
    baseline = json.load(f)

reference_date = baseline['metadata']['reference_date']
all_data = baseline['daily_ads']

print(f"📅 Reference date: {reference_date}")
print(f"📊 Total ads: {len(all_data)}")

# Calculer la semaine précédente (du 22 au 28 août si on est le 29)
prev_week_end = datetime.strptime(reference_date, '%Y-%m-%d') - timedelta(days=7)
prev_week_start = prev_week_end - timedelta(days=6)

print(f"📆 Previous week: {prev_week_start.strftime('%Y-%m-%d')} to {prev_week_end.strftime('%Y-%m-%d')}")

# Filtrer les ads de la semaine précédente
prev_week_ads = []
for ad in all_data:
    ad_date_str = ad.get('date')
    if ad_date_str:
        try:
            ad_date = datetime.strptime(ad_date_str, '%Y-%m-%d')
            if prev_week_start <= ad_date <= prev_week_end:
                prev_week_ads.append(ad)
        except:
            pass

print(f"✅ Found {len(prev_week_ads)} ads for previous week")

# Compter par compte
accounts = {}
for ad in prev_week_ads:
    acc = ad.get('account_name', 'Unknown')
    accounts[acc] = accounts.get(acc, 0) + 1

print("\n📊 Ads par compte:")
for acc, count in sorted(accounts.items(), key=lambda x: x[1], reverse=True)[:10]:
    print(f"  - {acc}: {count} ads")

# Sauvegarder
prev_total_spend = sum(float(ad.get('spend', 0)) for ad in prev_week_ads)
prev_output = {
    'metadata': {
        'timestamp': datetime.now().isoformat(),
        'reference_date': prev_week_end.strftime('%Y-%m-%d'),
        'date_range': f"{prev_week_start.strftime('%Y-%m-%d')} to {prev_week_end.strftime('%Y-%m-%d')}",
        'period_days': 7,
        'total_ads': len(prev_week_ads),
        'total_spend': prev_total_spend
    },
    'ads': prev_week_ads
}

with open('data/current/prev_week_data.json', 'w', encoding='utf-8') as f:
    json.dump(prev_output, f, indent=2, ensure_ascii=False)

print(f"\n💾 Saved prev_week_data.json")
print(f"💰 Total spend: ${prev_total_spend:,.0f}")

# Regenerer la compression
print("\n🗜️ Regénération des fichiers optimisés...")
import subprocess
result = subprocess.run(['python3', 'scripts/transform_to_columnar.py'], capture_output=True, text=True)
if result.returncode == 0:
    print("✅ Compression réussie")
else:
    print(f"❌ Erreur: {result.stderr}")