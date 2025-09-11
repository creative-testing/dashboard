#!/usr/bin/env python3
"""
Analyze ad naming patterns across ALL accounts to understand nomenclature chaos/order
"""
import json
from collections import defaultdict, Counter
import re
from pathlib import Path

def analyze_nomenclature_patterns():
    """Analyze all ad names to understand patterns"""
    
    # Load the optimized data
    meta_file = Path("docs/data/optimized/meta_v1.json")
    if not meta_file.exists():
        print("❌ No data found. Please run the data fetch first.")
        return
    
    with open(meta_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"\n{'='*80}")
    print(f"📊 ANÁLISIS COMPLETO DE NOMENCLATURA")
    print(f"{'='*80}\n")
    
    # Extract all ads with their metadata
    all_ads = []
    # The new format has 'ads' at the root level
    if 'ads' in data:
        all_ads = data['ads']
    else:
        # Fallback to old format
        for key, period_data in data.items():
            if isinstance(period_data, dict) and 'ads' in period_data:
                all_ads.extend(period_data['ads'])
    
    print(f"Total de anuncios analizados: {len(all_ads)}\n")
    
    # Group by account - handle both formats
    accounts_data = defaultdict(list)
    for ad in all_ads:
        # New format uses 'acc' and 'name', old format uses 'account_name' and 'ad_name'
        account = ad.get('account_name') or ad.get('acc', 'Unknown')
        # Store with normalized fields
        ad_normalized = {
            'account_name': account,
            'ad_name': ad.get('ad_name') or ad.get('name', ''),
            'ad_id': ad.get('ad_id') or ad.get('id', '')
        }
        accounts_data[account].append(ad_normalized)
    
    print(f"Total de cuentas: {len(accounts_data)}\n")
    
    # Analyze each account
    account_scores = {}
    
    for account_name, ads in accounts_data.items():
        print(f"\n{'='*60}")
        print(f"📁 CUENTA: {account_name}")
        print(f"   Anuncios: {len(ads)}")
        
        ad_names = [ad.get('ad_name', '') for ad in ads if ad.get('ad_name')]
        
        if not ad_names:
            print("   ⚠️ Sin nombres de anuncios")
            continue
        
        # 1. DELIMITER ANALYSIS
        delimiters = {
            'underscore': 0,
            'hyphen': 0,
            'pipe': 0,
            'space': 0,
            'none': 0
        }
        
        for name in ad_names:
            if '_' in name: delimiters['underscore'] += 1
            elif '-' in name: delimiters['hyphen'] += 1
            elif '|' in name: delimiters['pipe'] += 1
            elif ' ' in name: delimiters['space'] += 1
            else: delimiters['none'] += 1
        
        main_delimiter = max(delimiters, key=delimiters.get)
        delimiter_consistency = (delimiters[main_delimiter] / len(ad_names)) * 100
        
        print(f"\n   📋 CONSISTENCIA DE DELIMITADORES:")
        print(f"      Principal: {main_delimiter} ({delimiter_consistency:.1f}%)")
        
        # 2. SEGMENT ANALYSIS
        delimiter_char = {'underscore': '_', 'hyphen': '-', 'pipe': '|', 'space': ' '}.get(main_delimiter, None)
        
        segments_analysis = {
            'avg_segments': 0,
            'consistent_positions': {},
            'common_patterns': []
        }
        
        if delimiter_char:
            segment_counts = []
            position_values = defaultdict(Counter)
            
            for name in ad_names:
                if delimiter_char in name:
                    segments = name.split(delimiter_char)
                    segment_counts.append(len(segments))
                    
                    for i, segment in enumerate(segments[:10]):
                        # Normalize: lowercase, remove numbers for pattern detection
                        normalized = re.sub(r'\d+', '', segment.lower()).strip()
                        if normalized:
                            position_values[i][normalized] += 1
            
            if segment_counts:
                segments_analysis['avg_segments'] = sum(segment_counts) / len(segment_counts)
                
                # Find consistent patterns
                for pos, counter in position_values.items():
                    top_value, count = counter.most_common(1)[0]
                    consistency = (count / len(ad_names)) * 100
                    if consistency > 30:  # At least 30% consistency
                        segments_analysis['consistent_positions'][pos] = {
                            'value': top_value,
                            'consistency': consistency
                        }
        
        print(f"\n   🔍 ANÁLISIS DE SEGMENTOS:")
        print(f"      Promedio de segmentos: {segments_analysis['avg_segments']:.1f}")
        if segments_analysis['consistent_positions']:
            print(f"      Posiciones consistentes:")
            for pos, info in segments_analysis['consistent_positions'].items():
                print(f"         Posición {pos+1}: '{info['value']}' ({info['consistency']:.0f}%)")
        
        # 3. CONTENT PATTERN DETECTION
        patterns_found = {
            'has_dates': 0,
            'has_versions': 0,
            'has_nuevo_iteracion': 0,
            'has_angles': 0,
            'has_creators': 0,
            'has_products': 0,
            'has_campaigns': 0
        }
        
        # Common patterns to look for
        angle_keywords = ['problema', 'solucion', 'beneficio', 'precio', 'oferta', 'testimonio',
                         'picazon', 'olor', 'bienestar', 'salud', 'ansiedad', 'dolor']
        creator_patterns = [r'ugc', r'creator', r'@\w+', r'influencer']
        product_keywords = ['producto', 'item', 'sku', 'articulo']
        
        for name in ad_names:
            name_lower = name.lower()
            
            # Date patterns
            if re.search(r'\d{2,4}[-/]\d{1,2}[-/]\d{1,4}|\d{6,8}', name):
                patterns_found['has_dates'] += 1
            
            # Version patterns
            if re.search(r'[vV]\d+|v\d+\.\d+|iteracion|nuevo', name_lower):
                patterns_found['has_versions'] += 1
            
            # Nuevo/Iteración
            if 'nuevo' in name_lower or 'iteracion' in name_lower:
                patterns_found['has_nuevo_iteracion'] += 1
            
            # Angles
            if any(keyword in name_lower for keyword in angle_keywords):
                patterns_found['has_angles'] += 1
            
            # Creators
            if any(re.search(pattern, name_lower) for pattern in creator_patterns):
                patterns_found['has_creators'] += 1
            
            # Products
            if any(keyword in name_lower for keyword in product_keywords):
                patterns_found['has_products'] += 1
            
            # Campaign identifiers
            if re.search(r'camp\d+|campaign|q\d{1,2}', name_lower):
                patterns_found['has_campaigns'] += 1
        
        print(f"\n   🎯 PATRONES DETECTADOS:")
        for pattern, count in patterns_found.items():
            if count > 0:
                percentage = (count / len(ad_names)) * 100
                print(f"      {pattern}: {percentage:.1f}% ({count}/{len(ad_names)})")
        
        # 4. CALCULATE NOMENCLATURE SCORE
        score = 0
        
        # Delimiter consistency (30 points)
        if delimiter_consistency > 80:
            score += 30
        elif delimiter_consistency > 50:
            score += 15
        
        # Segment structure (30 points)
        if segments_analysis['avg_segments'] > 2 and segments_analysis['consistent_positions']:
            consistency_avg = sum(p['consistency'] for p in segments_analysis['consistent_positions'].values()) / len(segments_analysis['consistent_positions'])
            if consistency_avg > 50:
                score += 30
            elif consistency_avg > 30:
                score += 15
        
        # Pattern richness (40 points)
        pattern_coverage = sum(1 for v in patterns_found.values() if v > len(ad_names) * 0.1)
        if pattern_coverage >= 4:
            score += 40
        elif pattern_coverage >= 2:
            score += 20
        
        account_scores[account_name] = {
            'score': score,
            'total_ads': len(ads),
            'delimiter_consistency': delimiter_consistency,
            'avg_segments': segments_analysis['avg_segments'],
            'patterns': patterns_found
        }
        
        print(f"\n   📊 PUNTUACIÓN DE NOMENCLATURA: {score}/100")
        if score >= 70:
            print("      ✅ Excelente - Nomenclatura bien estructurada")
        elif score >= 40:
            print("      ⚠️ Moderada - Algunos patrones detectados")
        else:
            print("      ❌ Baja - Nomenclatura caótica o inexistente")
    
    # FINAL SUMMARY
    print(f"\n{'='*80}")
    print(f"📈 RESUMEN EJECUTIVO")
    print(f"{'='*80}\n")
    
    sorted_accounts = sorted(account_scores.items(), key=lambda x: x[1]['score'], reverse=True)
    
    excellent = [a for a, d in sorted_accounts if d['score'] >= 70]
    moderate = [a for a, d in sorted_accounts if 40 <= d['score'] < 70]
    poor = [a for a, d in sorted_accounts if d['score'] < 40]
    
    print("🏆 RANKING DE CUENTAS POR CALIDAD DE NOMENCLATURA:\n")
    for i, (account, data) in enumerate(sorted_accounts, 1):
        status = "✅" if data['score'] >= 70 else "⚠️" if data['score'] >= 40 else "❌"
        print(f"   {i}. {status} {account}: {data['score']}/100 ({data['total_ads']} ads)")
    
    print(f"\n📊 DISTRIBUCIÓN:")
    print(f"   ✅ Listas para análisis avanzado: {len(excellent)} cuentas")
    print(f"   ⚠️ Análisis parcial posible: {len(moderate)} cuentas")  
    print(f"   ❌ Necesitan mejorar nomenclatura: {len(poor)} cuentas")
    
    # RECOMMENDATIONS
    print(f"\n💡 RECOMENDACIONES PARA EL DASHBOARD:\n")
    
    if excellent:
        print("   1. CUENTAS CON ANÁLISIS COMPLETO:")
        for account in excellent[:3]:
            print(f"      • {account}")
        print("      → Mostrar gráficos de ángulos, creadores y segmentación")
    
    if moderate:
        print("\n   2. CUENTAS CON ANÁLISIS BÁSICO:")
        for account in moderate[:3]:
            print(f"      • {account}")
        print("      → Mostrar solo métricas detectables con confianza")
    
    if poor:
        print("\n   3. CUENTAS SIN ANÁLISIS DE NOMENCLATURA:")
        for account in poor[:3]:
            print(f"      • {account}")
        print("      → Ocultar sección de nomenclatura, mostrar solo KPIs básicos")
    
    print(f"\n🎯 ESTRATEGIA ADAPTATIVA PROPUESTA:")
    print("   • Score >= 70: Mostrar análisis completo de nomenclatura")
    print("   • Score 40-69: Mostrar análisis parcial con advertencia")
    print("   • Score < 40: Ocultar análisis, sugerir implementar nomenclatura")
    print("   • Siempre: Calcular score dinámicamente y ajustar UI")
    
    # Save report
    report = {
        'summary': {
            'total_accounts': len(account_scores),
            'total_ads': len(all_ads),
            'excellent_accounts': len(excellent),
            'moderate_accounts': len(moderate),
            'poor_accounts': len(poor)
        },
        'accounts': account_scores,
        'recommendations': {
            'full_analysis': excellent,
            'partial_analysis': moderate,
            'no_analysis': poor
        }
    }
    
    with open('nomenclature_analysis.json', 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\n📄 Reporte guardado en nomenclature_analysis.json")
    
    return report

if __name__ == "__main__":
    analyze_nomenclature_patterns()