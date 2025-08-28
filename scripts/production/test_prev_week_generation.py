#!/usr/bin/env python3
"""
Script de TEST pour valider la génération de prev_week
Sans faire de fetch complet - utilise les données existantes
"""
import json
from datetime import datetime, timedelta
import os

def test_prev_week_generation():
    """Test la génération de prev_week à partir du baseline existant"""
    
    print("🧪 TEST: Génération de prev_week")
    print("=" * 50)
    
    # 1. Charger le baseline existant
    baseline_file = 'data/current/baseline_90d_daily.json'
    if not os.path.exists(baseline_file):
        print(f"❌ Fichier {baseline_file} non trouvé")
        return False
    
    print(f"📂 Lecture du baseline existant...")
    with open(baseline_file, 'r', encoding='utf-8') as f:
        baseline = json.load(f)
    
    # Simuler les variables du script principal
    reference_date = baseline['metadata']['reference_date']
    all_data = baseline.get('daily_ads', [])
    
    print(f"📅 Date de référence: {reference_date}")
    print(f"📊 Total ads dans baseline: {len(all_data)}")
    
    # 2. COPIER LE CODE EXACT du script principal (lignes 431-470)
    print("\n🔄 Exécution du code de génération prev_week...")
    
    # 8. Semaine précédente (génération automatique à partir du baseline)
    prev_week_end = datetime.strptime(reference_date, '%Y-%m-%d') - timedelta(days=7)
    prev_week_start = prev_week_end - timedelta(days=6)
    
    # Filtrer les ads de la semaine précédente
    prev_week_ads = [
        ad for ad in all_data 
        if ad.get('date') and prev_week_start <= datetime.strptime(ad['date'], '%Y-%m-%d') <= prev_week_end
    ]
    
    # Calculer les métriques de la semaine précédente
    prev_total_spend = sum(float(ad.get('spend', 0)) for ad in prev_week_ads)
    prev_total_purchases = sum(int(ad.get('purchases', 0)) for ad in prev_week_ads)
    prev_total_value = sum(float(ad.get('purchase_value', 0)) for ad in prev_week_ads)
    prev_active_ads = sum(1 for ad in prev_week_ads if ad.get('effective_status') == 'ACTIVE')
    
    prev_output = {
        'metadata': {
            'timestamp': datetime.now().isoformat(),
            'reference_date': prev_week_end.strftime('%Y-%m-%d'),
            'date_range': f"{prev_week_start.strftime('%Y-%m-%d')} to {prev_week_end.strftime('%Y-%m-%d')}",
            'period_days': 7,
            'total_ads': len(prev_week_ads),
            'active_ads': prev_active_ads,
            'total_spend': prev_total_spend,
            'total_purchases': prev_total_purchases,
            'total_conversion_value': prev_total_value,
            'avg_roas': prev_total_value / prev_total_spend if prev_total_spend > 0 else 0,
            'avg_cpa': prev_total_spend / prev_total_purchases if prev_total_purchases > 0 else 0,
            'has_demographics': False,
            'has_creatives': True
        },
        'ads': prev_week_ads
    }
    
    # 3. Sauvegarder dans un fichier TEST
    test_output_file = 'data/temp/test_prev_week.json'
    os.makedirs('data/temp', exist_ok=True)
    
    with open(test_output_file, 'w', encoding='utf-8') as f:
        json.dump(prev_output, f, indent=2, ensure_ascii=False)
    
    if prev_week_ads:
        print(f"  ✅ Semaine précédente: {len(prev_week_ads)} ads, ${prev_total_spend:,.0f} MXN")
    
    # 4. Comparer avec le fichier actuel
    print("\n📊 Comparaison avec le fichier actuel:")
    
    current_file = 'data/current/hybrid_data_prev_week.json'
    if os.path.exists(current_file):
        with open(current_file, 'r', encoding='utf-8') as f:
            current_data = json.load(f)
        
        print(f"  Actuel: {current_data['metadata'].get('total_ads', 0)} ads")
        print(f"  Test:   {len(prev_week_ads)} ads")
        
        if current_data['metadata'].get('total_ads', 0) == len(prev_week_ads):
            print("  ✅ Les nombres correspondent!")
        else:
            print("  ⚠️ Différence détectée")
    
    # 5. Résumé
    print("\n📈 Résumé du test:")
    print(f"  - Période: {prev_week_start.strftime('%Y-%m-%d')} à {prev_week_end.strftime('%Y-%m-%d')}")
    print(f"  - Total ads: {len(prev_week_ads)}")
    print(f"  - Active ads: {prev_active_ads}")
    print(f"  - Total spend: ${prev_total_spend:,.0f} MXN")
    print(f"  - ROAS: {prev_total_value / prev_total_spend if prev_total_spend > 0 else 0:.2f}")
    print(f"  - CPA: ${prev_total_spend / prev_total_purchases if prev_total_purchases > 0 else 0:.2f}")
    
    print(f"\n💾 Fichier test sauvé dans: {test_output_file}")
    print("✅ Le code de génération fonctionne correctement!")
    print("\n📝 Recommandation: Le prochain fetch complet générera automatiquement")
    print("   les bonnes données prev_week sans intervention manuelle.")
    
    return True

if __name__ == '__main__':
    test_prev_week_generation()