#!/usr/bin/env python3
"""
Rapport COMPLET de nomenclature avec toutes les données
Période: 7-12 septembre 2025
"""

import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime

def count_real_slashes(ad_name):
    """Compte les slashes en traitant N/A comme un seul élément"""
    temp = ad_name.replace('N/A', '{{NA}}').replace('n/a', '{{NA}}')
    return temp.count('/')

def get_real_parts(ad_name):
    """Récupère les parties en gérant N/A"""
    temp = ad_name.replace('N/A', '{{NA}}').replace('n/a', '{{NA}}')
    parts = temp.split('/')
    parts = [p.replace('{{NA}}', 'N/A').strip() for p in parts]
    return [p for p in parts if p]

# Charger les données
data_path = Path(__file__).parent.parent.parent / 'data' / 'current' / 'baseline_90d_daily.json'

print("=" * 100)
print("📊 INFORME COMPLETO DE CONFORMIDAD DE NOMENCLATURA")
print("=" * 100)

with open(data_path) as f:
    data = json.load(f)

# Filtrer les pubs depuis le 7 septembre
ads = [ad for ad in data.get('daily_ads', []) 
       if ad.get('created_time', '') >= '2025-09-07']

print(f"\n📅 Período analizado: 7-12 de septiembre 2025")
print(f"📈 Total de anuncios: {len(ads)}")

# Analyser par période
period1_ads = [ad for ad in ads if '2025-09-07' <= ad.get('created_time', '') <= '2025-09-10']
period2_ads = [ad for ad in ads if ad.get('created_time', '') >= '2025-09-11']

print(f"\n   Período 1 (7-10 sept): {len(period1_ads)} anuncios")
print(f"   Período 2 (11-12 sept): {len(period2_ads)} anuncios")

# Analyser par compte
by_account = defaultdict(lambda: {'total': [], 'period1': [], 'period2': []})

for ad in ads:
    account = ad.get('account_name', 'Unknown')
    slashes = count_real_slashes(ad['ad_name'])
    
    entry = {
        'name': ad['ad_name'],
        'slashes': slashes,
        'correct': slashes == 4,
        'spend': float(ad.get('spend', 0)),
        'date': ad.get('created_time', '')
    }
    
    by_account[account]['total'].append(entry)
    
    if ad.get('created_time', '') <= '2025-09-10':
        by_account[account]['period1'].append(entry)
    else:
        by_account[account]['period2'].append(entry)

# Calculer les statistiques
accounts_perfect = []
accounts_good = []  # >80% correct
accounts_medium = []  # 50-80% correct
accounts_bad = []  # <50% correct
accounts_zero = []  # 0% correct

print("\n" + "=" * 100)
print("RESULTADOS POR CUENTA")
print("=" * 100)

all_results = []

for account, data_acc in by_account.items():
    total = len(data_acc['total'])
    correct = sum(1 for ad in data_acc['total'] if ad['correct'])
    incorrect = total - correct
    pct = (correct / total * 100) if total > 0 else 0
    
    # Évolution
    p1_total = len(data_acc['period1'])
    p1_correct = sum(1 for ad in data_acc['period1'] if ad['correct']) if p1_total > 0 else 0
    p1_pct = (p1_correct / p1_total * 100) if p1_total > 0 else 0
    
    p2_total = len(data_acc['period2'])
    p2_correct = sum(1 for ad in data_acc['period2'] if ad['correct']) if p2_total > 0 else 0
    p2_pct = (p2_correct / p2_total * 100) if p2_total > 0 else 0
    
    evolution = ""
    if p1_total > 0 and p2_total > 0:
        if p2_pct > p1_pct + 10:
            evolution = "📈 MEJORÓ"
        elif p2_pct < p1_pct - 10:
            evolution = "📉 EMPEORÓ"
        else:
            evolution = "➡️ ESTABLE"
    elif p2_total > 0:
        evolution = "🆕 NUEVO"
    
    result = {
        'account': account,
        'total': total,
        'correct': correct,
        'incorrect': incorrect,
        'pct': pct,
        'p1_pct': p1_pct,
        'p2_pct': p2_pct,
        'evolution': evolution
    }
    
    all_results.append(result)
    
    # Categorizar
    if pct == 100:
        accounts_perfect.append(result)
    elif pct > 80:
        accounts_good.append(result)
    elif pct >= 50:
        accounts_medium.append(result)
    elif pct > 0:
        accounts_bad.append(result)
    else:
        accounts_zero.append(result)

# Ordenar por porcentaje
all_results.sort(key=lambda x: x['pct'], reverse=True)

print("\n✅ CUENTAS PERFECTAS (100% conformidad)")
print("-" * 80)
for acc in accounts_perfect:
    print(f"{acc['account']}: {acc['correct']}/{acc['total']} ✅ {acc['evolution']}")

print("\n⚠️ CUENTAS MIXTAS")
print("-" * 80)
for acc in accounts_good + accounts_medium + accounts_bad:
    status = "🟢" if acc['pct'] > 80 else "🟡" if acc['pct'] >= 50 else "🔴"
    print(f"{status} {acc['account']}: {acc['correct']}/{acc['total']} ({acc['pct']:.0f}%) {acc['evolution']}")
    if acc['incorrect'] > 0:
        # Mostrar ejemplo de error
        for ad in acc['account'] in by_account and by_account[acc['account']]['total']:
            if not ad['correct']:
                print(f"   ❌ Ejemplo: \"{ad['name'][:60]}...\" ({ad['slashes']} slashes)")
                break

print("\n❌ CUENTAS PROBLEMÁTICAS (0% conformidad)")
print("-" * 80)
for acc in accounts_zero:
    print(f"💀 {acc['account']}: 0/{acc['total']} (0%) {acc['evolution']}")
    # Mostrar tipos de errores
    slash_counts = defaultdict(int)
    for ad in by_account[acc['account']]['total']:
        slash_counts[ad['slashes']] += 1
    print(f"   Distribución: {dict(slash_counts)}")

# Estadísticas globales
total_correct = sum(acc['correct'] for acc in all_results)
total_ads = len(ads)
global_pct = (total_correct / total_ads * 100) if total_ads > 0 else 0

print("\n" + "=" * 100)
print("📊 RESUMEN EJECUTIVO")
print("=" * 100)
print(f"\n✅ Conformidad global: {total_correct}/{total_ads} ({global_pct:.1f}%)")
print(f"\nDistribución de cuentas ({len(all_results)} total):")
print(f"  🌟 Perfectas (100%): {len(accounts_perfect)} cuentas")
print(f"  🟢 Buenas (>80%): {len(accounts_good)} cuentas")
print(f"  🟡 Medias (50-80%): {len(accounts_medium)} cuentas")
print(f"  🔴 Malas (<50%): {len(accounts_bad)} cuentas")
print(f"  💀 Cero (0%): {len(accounts_zero)} cuentas")

# Top 10 problemas por volumen
print("\n🚨 TOP 10 CUENTAS A CORREGIR (por volumen de errores):")
print("-" * 80)
all_results.sort(key=lambda x: x['incorrect'], reverse=True)
for i, acc in enumerate(all_results[:10], 1):
    if acc['incorrect'] > 0:
        print(f"{i}. {acc['account']}: {acc['incorrect']} anuncios incorrectos")

# Evolución
print("\n📈 EVOLUCIÓN (Período 1 vs Período 2):")
print("-" * 80)
improved = [acc for acc in all_results if "MEJORÓ" in acc['evolution']]
worsened = [acc for acc in all_results if "EMPEORÓ" in acc['evolution']]

if improved:
    print("Mejoraron:")
    for acc in improved:
        print(f"  📈 {acc['account']}: {acc['p1_pct']:.0f}% → {acc['p2_pct']:.0f}%")

if worsened:
    print("\nEmpeoraron:")
    for acc in worsened:
        print(f"  📉 {acc['account']}: {acc['p1_pct']:.0f}% → {acc['p2_pct']:.0f}%")

print("\n" + "=" * 100)
print("Informe generado el", datetime.now().strftime("%d/%m/%Y %H:%M"))
print("Datos actualizados hasta el 12 de septiembre 2025")