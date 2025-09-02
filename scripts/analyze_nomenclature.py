#!/usr/bin/env python3
"""
Analyze ad naming patterns across all accounts to understand nomenclature usage
"""
import json
import re
from collections import defaultdict, Counter
from pathlib import Path

def analyze_nomenclature():
    """Analyze ad naming patterns from processed data"""
    
    # Load processed data
    data_file = Path("docs/data/processed_last_7d.json")
    if not data_file.exists():
        print("❌ No processed data found. Run fetch_with_smart_limits.py first.")
        return
    
    with open(data_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    ads = data.get('data', [])
    print(f"\n📊 ANALYZING NOMENCLATURE PATTERNS")
    print(f"{'='*80}")
    print(f"Total ads analyzed: {len(ads)}")
    
    # Group by account
    accounts = defaultdict(list)
    for ad in ads:
        account_name = ad.get('account_name', 'Unknown')
        accounts[account_name].append(ad)
    
    print(f"Total accounts: {len(accounts)}")
    print()
    
    # Analyze each account
    account_analysis = {}
    
    for account_name, account_ads in accounts.items():
        print(f"\n{'='*80}")
        print(f"📁 ACCOUNT: {account_name}")
        print(f"   Ads: {len(account_ads)}")
        
        # Collect all ad names
        ad_names = [ad.get('ad_name', '') for ad in account_ads if ad.get('ad_name')]
        
        if not ad_names:
            print("   ⚠️ No ad names found")
            continue
        
        # Analyze patterns
        analysis = {
            'total_ads': len(account_ads),
            'ad_names': ad_names,
            'patterns': {},
            'common_elements': {},
            'nomenclature_score': 0
        }
        
        # 1. Check for delimiter patterns
        delimiters = {
            'underscore': 0,  # word_word
            'hyphen': 0,      # word-word
            'pipe': 0,        # word|word
            'dot': 0,         # word.word
            'space': 0,       # word word
            'mixed': 0        # combination
        }
        
        for name in ad_names:
            if '_' in name: delimiters['underscore'] += 1
            if '-' in name: delimiters['hyphen'] += 1
            if '|' in name: delimiters['pipe'] += 1
            if '.' in name and not name.endswith('.mp4') and not name.endswith('.jpg'): delimiters['dot'] += 1
            if ' ' in name: delimiters['space'] += 1
        
        print(f"\n   📋 DELIMITER USAGE:")
        for delim, count in sorted(delimiters.items(), key=lambda x: x[1], reverse=True):
            if count > 0:
                percentage = (count / len(ad_names)) * 100
                print(f"      {delim}: {count}/{len(ad_names)} ({percentage:.1f}%)")
        
        # 2. Identify common patterns/segments
        segments_by_position = defaultdict(Counter)
        
        # Try to split names by most common delimiter
        main_delimiter = max(delimiters, key=delimiters.get) if max(delimiters.values()) > 0 else None
        
        if main_delimiter:
            delimiter_char = {
                'underscore': '_',
                'hyphen': '-',
                'pipe': '|',
                'dot': '.',
                'space': ' '
            }.get(main_delimiter, ' ')
            
            print(f"\n   🔍 ANALYZING SEGMENTS (using '{delimiter_char}' as delimiter):")
            
            for name in ad_names:
                if delimiter_char in name:
                    segments = name.split(delimiter_char)
                    for i, segment in enumerate(segments[:10]):  # Max 10 segments
                        segments_by_position[i][segment.lower()] += 1
            
            # Show most common values per position
            for position, counter in sorted(segments_by_position.items())[:5]:
                top_values = counter.most_common(5)
                if top_values:
                    print(f"\n      Position {position+1}:")
                    for value, count in top_values:
                        if count > 1:  # Only show if appears more than once
                            print(f"         '{value}': {count}x")
        
        # 3. Look for specific patterns (angles, creators, formats, etc.)
        patterns_found = {
            'has_dates': [],
            'has_creators': [],
            'has_angles': [],
            'has_formats': [],
            'has_versions': [],
            'has_ids': []
        }
        
        # Common angle keywords (from Petcare analysis)
        angle_keywords = ['picazon', 'olor', 'caida', 'pelo', 'pelaje', 'beneficios', 
                         'promo', 'descuento', 'oferta', 'gratis', 'regalo',
                         'nuevo', 'testimonio', 'veterinario', 'ciencia']
        
        # Common creator indicators
        creator_patterns = [r'UGC', r'creator', r'influencer', r'@\w+']
        
        # Format indicators
        format_keywords = ['video', 'imagen', 'carousel', 'reel', 'story', 'static', 'dynamic']
        
        print(f"\n   🎯 PATTERN DETECTION:")
        
        for name in ad_names:
            name_lower = name.lower()
            
            # Check for dates (YYYY-MM-DD, DD/MM/YYYY, etc.)
            if re.search(r'\d{2,4}[-/]\d{1,2}[-/]\d{1,4}', name):
                patterns_found['has_dates'].append(name)
            
            # Check for angles
            for keyword in angle_keywords:
                if keyword in name_lower:
                    patterns_found['has_angles'].append(name)
                    break
            
            # Check for creators
            for pattern in creator_patterns:
                if re.search(pattern, name, re.IGNORECASE):
                    patterns_found['has_creators'].append(name)
                    break
            
            # Check for formats
            for keyword in format_keywords:
                if keyword in name_lower:
                    patterns_found['has_formats'].append(name)
                    break
            
            # Check for versions (v1, v2, V01, etc.)
            if re.search(r'[vV]\d+', name):
                patterns_found['has_versions'].append(name)
            
            # Check for IDs (long numbers or hex strings)
            if re.search(r'\d{6,}|[a-f0-9]{8,}', name, re.IGNORECASE):
                patterns_found['has_ids'].append(name)
        
        for pattern_type, names_with_pattern in patterns_found.items():
            if names_with_pattern:
                percentage = (len(names_with_pattern) / len(ad_names)) * 100
                print(f"      {pattern_type}: {len(names_with_pattern)}/{len(ad_names)} ({percentage:.1f}%)")
                # Show examples
                for example in names_with_pattern[:2]:  # Show max 2 examples
                    print(f"         Example: '{example[:60]}...'")
        
        # 4. Calculate nomenclature consistency score
        score = 0
        max_score = 100
        
        # Consistent delimiter usage (40 points)
        if main_delimiter and delimiters[main_delimiter] > len(ad_names) * 0.8:
            score += 40
        elif main_delimiter and delimiters[main_delimiter] > len(ad_names) * 0.5:
            score += 20
        
        # Has structured segments (30 points)
        if segments_by_position:
            # Check if first segments are consistent
            first_segment_consistency = 0
            if 0 in segments_by_position:
                top_value_count = segments_by_position[0].most_common(1)[0][1]
                first_segment_consistency = top_value_count / len(ad_names)
            
            if first_segment_consistency > 0.5:
                score += 30
            elif first_segment_consistency > 0.3:
                score += 15
        
        # Has identifiable patterns (30 points)
        patterns_coverage = sum(len(v) for v in patterns_found.values()) / len(ad_names)
        if patterns_coverage > 0.7:
            score += 30
        elif patterns_coverage > 0.4:
            score += 15
        
        analysis['nomenclature_score'] = score
        
        print(f"\n   📊 NOMENCLATURE CONSISTENCY SCORE: {score}/100")
        if score >= 70:
            print("      ✅ Excellent - Strong nomenclature patterns")
        elif score >= 40:
            print("      ⚠️ Moderate - Some patterns detected")
        else:
            print("      ❌ Poor - Little to no consistent nomenclature")
        
        account_analysis[account_name] = analysis
    
    # Summary
    print(f"\n{'='*80}")
    print(f"📈 SUMMARY")
    print(f"{'='*80}")
    
    # Rank accounts by nomenclature score
    sorted_accounts = sorted(account_analysis.items(), 
                           key=lambda x: x[1]['nomenclature_score'], 
                           reverse=True)
    
    print("\n🏆 ACCOUNT RANKING BY NOMENCLATURE QUALITY:")
    for i, (account_name, analysis) in enumerate(sorted_accounts, 1):
        score = analysis['nomenclature_score']
        status = "✅" if score >= 70 else "⚠️" if score >= 40 else "❌"
        print(f"   {i}. {status} {account_name}: {score}/100")
    
    # Overall recommendations
    print("\n💡 RECOMMENDATIONS:")
    
    high_quality = [a for a, d in account_analysis.items() if d['nomenclature_score'] >= 70]
    medium_quality = [a for a, d in account_analysis.items() if 40 <= d['nomenclature_score'] < 70]
    low_quality = [a for a, d in account_analysis.items() if d['nomenclature_score'] < 40]
    
    if high_quality:
        print(f"\n   ✅ READY FOR FULL ANALYSIS ({len(high_quality)} accounts):")
        for account in high_quality[:5]:
            print(f"      • {account}")
        print("      → These accounts have consistent nomenclature")
        print("      → Can enable advanced creative angle analysis")
    
    if medium_quality:
        print(f"\n   ⚠️ PARTIAL ANALYSIS POSSIBLE ({len(medium_quality)} accounts):")
        for account in medium_quality[:5]:
            print(f"      • {account}")
        print("      → These accounts have some patterns")
        print("      → Can detect basic patterns but may miss details")
    
    if low_quality:
        print(f"\n   ❌ NEED NOMENCLATURE IMPROVEMENT ({len(low_quality)} accounts):")
        for account in low_quality[:5]:
            print(f"      • {account}")
        print("      → These accounts lack consistent naming")
        print("      → Recommend implementing naming conventions")
    
    # Save detailed report
    report = {
        'summary': {
            'total_accounts': len(accounts),
            'total_ads': len(ads),
            'high_quality_accounts': len(high_quality),
            'medium_quality_accounts': len(medium_quality),
            'low_quality_accounts': len(low_quality)
        },
        'accounts': account_analysis,
        'recommendations': {
            'ready_for_analysis': high_quality,
            'partial_analysis': medium_quality,
            'needs_improvement': low_quality
        }
    }
    
    with open('nomenclature_analysis.json', 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\n📄 Detailed report saved to nomenclature_analysis.json")
    
    return report

if __name__ == "__main__":
    analyze_nomenclature()