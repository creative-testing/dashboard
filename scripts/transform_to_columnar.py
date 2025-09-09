#!/usr/bin/env python3
"""
Version 2 du script de transformation vers format columnar.
Lit directement depuis baseline_90d_daily.json sans passer par les fichiers hybrid.
Élimine une étape inutile et évite les problèmes de synchronisation de dates.
"""

import os
import json
import sys
from datetime import datetime, timedelta
from collections import defaultdict

def load_json(filepath):
    """Load JSON file efficiently"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(data, filepath):
    """Save JSON file with compact format"""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, separators=(',', ':'), ensure_ascii=False)

def transform_data(input_dir='data/current', output_dir='data/optimized'):
    """
    Transform baseline data directly to columnar format.
    Skip the hybrid files step entirely.
    """
    
    # 1. Load baseline data (source of truth)
    baseline_path = os.path.join(input_dir, 'baseline_90d_daily.json')
    if not os.path.exists(baseline_path):
        print(f"❌ Baseline file not found: {baseline_path}")
        return False
    
    print(f"📖 Loading baseline data from {baseline_path}...")
    baseline_data = load_json(baseline_path)
    
    # Extract metadata
    metadata = baseline_data.get('metadata', {})
    reference_date = metadata.get('reference_date')
    if not reference_date:
        print("⚠️ No reference_date found, using today-1")
        reference_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    print(f"📅 Reference date: {reference_date}")
    
    all_daily_ads = baseline_data.get('daily_ads', [])
    print(f"📊 Total daily records: {len(all_daily_ads):,}")
    
    # 2. Aggregate by ad_id and period
    print("\n🔄 Aggregating data by period...")
    
    # Determine available periods based on data range
    min_date = min(ad['date'] for ad in all_daily_ads if ad.get('date'))
    max_date = max(ad['date'] for ad in all_daily_ads if ad.get('date'))
    min_dt = datetime.strptime(min_date, '%Y-%m-%d')
    max_dt = datetime.strptime(max_date, '%Y-%m-%d')
    data_range_days = (max_dt - min_dt).days + 1
    
    # Only include periods that we have data for
    all_periods = ['3d', '7d', '14d', '30d', '90d']
    periods = []
    for p in all_periods:
        period_days = int(p.replace('d', ''))
        if data_range_days >= period_days:
            periods.append(p)
        else:
            # Still include the period but it will have same data as the previous one
            periods.append(p)
    
    print(f"📊 Data range: {data_range_days} days ({min_date} to {max_date})")
    print(f"📋 Periods to process: {periods}")
    
    aggregated_by_period = defaultdict(lambda: defaultdict(lambda: {
        'impressions': 0,
        'clicks': 0,
        'spend': 0.0,
        'purchases': 0,
        'purchase_value': 0.0,
        'reach': 0
    }))
    
    # Calculate cutoff dates for each period
    reference_dt = datetime.strptime(reference_date, '%Y-%m-%d')
    cutoff_dates = {}
    for period in periods:
        days = int(period.replace('d', ''))
        # If period is larger than data range, use min_date as cutoff
        if days > data_range_days:
            cutoff_dates[period] = min_date
        else:
            cutoff_dates[period] = (reference_dt - timedelta(days=days-1)).strftime('%Y-%m-%d')
    
    print(f"📈 Period cutoff dates:")
    for period, cutoff in cutoff_dates.items():
        print(f"   {period}: from {cutoff} to {reference_date}")
    
    # Process all ads once, aggregating for each period
    for ad in all_daily_ads:
        ad_id = ad.get('ad_id')
        if not ad_id:
            continue
        
        ad_date = ad.get('date')
        if not ad_date:
            continue
        
        # Check which periods this ad belongs to
        for period in periods:
            if ad_date >= cutoff_dates[period]:
                agg = aggregated_by_period[period][ad_id]
                
                # Aggregate metrics
                agg['impressions'] += int(ad.get('impressions', 0))
                agg['clicks'] += int(ad.get('clicks', 0))
                agg['spend'] += float(ad.get('spend', 0))
                agg['purchases'] += int(ad.get('purchases', 0))
                agg['purchase_value'] += float(ad.get('purchase_value', 0))
                # IMPORTANT: Reach est NON-ADDITIVE - on ne peut pas sommer les reach journalières
                # La reach d'une période = personnes uniques, pas la somme des reach journalières
                # Pour l'instant on met à 0, nécessite un appel API séparé pour avoir la vraie valeur
                # agg['reach'] += int(ad.get('reach', 0))  # INCORRECT - commenté
                
                # Keep first occurrence metadata
                if 'ad_name' not in agg:
                    agg['ad_name'] = ad.get('ad_name', '')
                    agg['campaign_name'] = ad.get('campaign_name', '')
                    agg['campaign_id'] = ad.get('campaign_id', '')
                    agg['adset_name'] = ad.get('adset_name', '')
                    agg['adset_id'] = ad.get('adset_id', '')
                    agg['account_name'] = ad.get('account_name', '')
                    agg['account_id'] = ad.get('account_id', '')
                    agg['status'] = ad.get('status', 'UNKNOWN')
                    agg['effective_status'] = ad.get('effective_status', 'UNKNOWN')
                    agg['format'] = ad.get('format', 'UNKNOWN')
                    agg['media_url'] = ad.get('media_url', '')
                    agg['created_time'] = ad.get('created_time', '')
    
    # Report aggregation results
    for period in periods:
        ad_count = len(aggregated_by_period[period])
        total_spend = sum(ad['spend'] for ad in aggregated_by_period[period].values())
        print(f"✅ {period}: {ad_count:,} unique ads, ${total_spend:,.0f} spend")
    
    # 3. Build columnar structures
    print("\n🏗️ Building columnar format...")
    
    # Use the largest available period as base to include ALL ads
    # In TAIL mode, this will be 3d or 7d; in BASELINE mode, this will be 90d
    # This ensures we capture all ads regardless of the fetch mode
    base_period = periods[-1]  # Last period is always the largest (3d, 7d, 14d, 30d, 90d)
    base_ads = aggregated_by_period[base_period]
    print(f"📦 Using {base_period} as base period ({len(base_ads)} unique ads)")
    
    # Sort ads by spend (descending) for better compression
    sorted_ads = sorted(base_ads.items(), key=lambda x: x[1]['spend'], reverse=True)
    
    # Build entity dictionaries
    campaigns = {}
    adsets = {}
    accounts = {}
    
    # Build columnar data
    ad_ids = []
    values = []
    meta_ads = []
    
    for ad_id, ad_data in sorted_ads:
        # Extract entity data
        campaign_id = ad_data['campaign_id']
        adset_id = ad_data['adset_id']
        account_id = ad_data['account_id']
        
        # Store unique entities
        if campaign_id and campaign_id not in campaigns:
            campaigns[campaign_id] = {'name': ad_data['campaign_name']}
        
        if adset_id and adset_id not in adsets:
            adsets[adset_id] = {'name': ad_data['adset_name']}
        
        if account_id and account_id not in accounts:
            accounts[account_id] = {'name': ad_data['account_name']}
        
        # Add to columnar arrays
        ad_ids.append(ad_id)
        
        # Add values for each period (flattened array)
        for period in periods:
            period_data = aggregated_by_period[period].get(ad_id, {})
            values.extend([
                period_data.get('impressions', 0),
                period_data.get('clicks', 0),
                period_data.get('purchases', 0),
                int(period_data.get('spend', 0) * 100),  # Store as cents
                int(period_data.get('purchase_value', 0) * 100),  # Store as cents
                period_data.get('reach', 0)
            ])
        
        # Add metadata
        meta_ads.append({
            "id": ad_id,
            "name": ad_data['ad_name'][:100] if ad_data.get('ad_name') else '',
            "cid": campaign_id,
            "aid": adset_id,
            "acc": account_id,
            "format": ad_data.get('format', 'UNKNOWN'),
            "status": ad_data.get('effective_status', 'UNKNOWN'),
            "media": ad_data.get('media_url', ''),  # Full URL, no truncation
            "ct": ad_data.get('created_time', '')
        })
    
    # 4. Build output files
    print("📝 Writing optimized files...")
    os.makedirs(output_dir, exist_ok=True)
    
    # agg_v1.json - Columnar metrics data
    agg_data = {
        "version": 1,
        "periods": periods,
        "metrics": ["impressions", "clicks", "purchases", "spend", "purchase_value", "reach"],
        "ads": ad_ids,
        "values": values,
        "scales": {"money": 100}  # Cents to dollars
    }
    save_json(agg_data, f"{output_dir}/agg_v1.json")
    print(f"  ✓ agg_v1.json ({len(ad_ids)} ads)")
    
    # meta_v1.json - Entity metadata
    # Propager les nouvelles métadonnées de fraîcheur
    reference_hour = baseline_data.get('metadata', {}).get('reference_hour')
    buffer_hours = baseline_data.get('metadata', {}).get('buffer_hours')
    includes_today = baseline_data.get('metadata', {}).get('includes_today', False)
    
    meta_data = {
        "version": 1,
        "metadata": {
            "reference_date": reference_date,
            "reference_hour": reference_hour,
            "buffer_hours": buffer_hours,
            "includes_today": includes_today,
            "data_min_date": min_date,
            "data_max_date": max_date,
            "data_range_days": data_range_days,
            "last_update": datetime.now().isoformat(),
            "source": "baseline_90d_daily.json",
            "pipeline": "v2_direct_from_baseline"
        },
        "ads": meta_ads,
        "campaigns": campaigns,
        "adsets": adsets,
        "accounts": accounts
    }
    save_json(meta_data, f"{output_dir}/meta_v1.json")
    print(f"  ✓ meta_v1.json ({len(campaigns)} campaigns, {len(accounts)} accounts)")
    
    # summary_v1.json - Period totals
    summary_totals = {}
    for period in periods:
        period_ads = aggregated_by_period[period]
        if period_ads:
            summary_totals[period] = {
                "impr": sum(ad.get('impressions', 0) for ad in period_ads.values()),
                "clk": sum(ad.get('clicks', 0) for ad in period_ads.values()),
                "purch": sum(ad.get('purchases', 0) for ad in period_ads.values()),
                "spend_cents": int(sum(ad.get('spend', 0) for ad in period_ads.values()) * 100),
                "purchase_value_cents": int(sum(ad.get('purchase_value', 0) for ad in period_ads.values()) * 100),
                "reach": 0  # Reach est non-additive, ne peut pas être sommée
            }
        else:
            summary_totals[period] = {
                "impr": 0, "clk": 0, "purch": 0,
                "spend_cents": 0, "purchase_value_cents": 0, "reach": 0
            }
    
    summary_data = {
        "periods": periods,
        "totals": summary_totals
    }
    save_json(summary_data, f"{output_dir}/summary_v1.json")
    print(f"  ✓ summary_v1.json")
    
    # manifest.json
    manifest_data = {
        "version": datetime.now().isoformat(),
        "ads_count": len(ad_ids),
        "periods": periods,
        "shards": {
            "meta": {"path": "meta_v1.json"},
            "agg": {"path": "agg_v1.json"},
            "summary": {"path": "summary_v1.json"}
        }
    }
    save_json(manifest_data, f"{output_dir}/manifest.json")
    print(f"  ✓ manifest.json")
    
    # 5. Handle previous week data if exists
    prev_week_path = os.path.join(input_dir, 'prev_week_data.json')
    if os.path.exists(prev_week_path):
        print("\n🗜️ Compressing previous week data...")
        prev_week_data = load_json(prev_week_path)
        
        # Aggregate by ad_id
        prev_week_aggregated = defaultdict(lambda: {
            'impressions': 0,
            'clicks': 0,
            'spend': 0.0,
            'purchases': 0,
            'purchase_value': 0.0,
            'reach': 0
        })
        
        for ad in prev_week_data.get('ads', []):
            ad_id = ad.get('ad_id')
            if ad_id:
                agg = prev_week_aggregated[ad_id]
                agg['impressions'] += int(ad.get('impressions', 0))
                agg['clicks'] += int(ad.get('clicks', 0))
                agg['spend'] += float(ad.get('spend', 0))
                agg['purchases'] += int(ad.get('purchases', 0))
                agg['purchase_value'] += float(ad.get('purchase_value', 0))
                # Reach non-additive - ignorée dans l'agrégation
                # agg['reach'] += int(ad.get('reach', 0))
                
                # Keep metadata from first occurrence
                if 'ad_name' not in agg:
                    for key in ['ad_name', 'campaign_name', 'adset_name', 'account_name']:
                        agg[key] = ad.get(key, '')
        
        # Convert back to list format
        compressed_ads = []
        for ad_id, data in prev_week_aggregated.items():
            compressed_ads.append({
                'ad_id': ad_id,
                'ad_name': data.get('ad_name', ''),
                'campaign_name': data.get('campaign_name', ''),
                'adset_name': data.get('adset_name', ''),
                'account_name': data.get('account_name', ''),
                'impressions': data['impressions'],
                'clicks': data['clicks'],
                'spend': data['spend'],
                'purchases': data['purchases'],
                'purchase_value': data['purchase_value'],
                'reach': data['reach']
            })
        
        prev_week_compressed = {
            'period': 'prev_week',
            'ads': compressed_ads
        }
        
        save_json(prev_week_compressed, f"{output_dir}/prev_week_compressed.json")
        print(f"  ✓ prev_week_compressed.json ({len(compressed_ads)} ads)")
    
    return True

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Transform baseline data directly to columnar format')
    parser.add_argument('--input-dir', default='data/current', help='Input directory')
    parser.add_argument('--output-dir', default='data/optimized', help='Output directory')
    args = parser.parse_args()
    
    print("🚀 Transformation V2 - Direct from baseline")
    print("=" * 50)
    
    success = transform_data(args.input_dir, args.output_dir)
    
    if success:
        print("\n✅ Transformation successful!")
        
        # Report file sizes
        output_dir = args.output_dir
        total_size = 0
        for filename in ['meta_v1.json', 'agg_v1.json', 'summary_v1.json', 'manifest.json']:
            filepath = os.path.join(output_dir, filename)
            if os.path.exists(filepath):
                size = os.path.getsize(filepath) / 1024 / 1024
                total_size += size
                print(f"  {filename}: {size:.2f} MB")
        
        print(f"\n📊 Total optimized size: {total_size:.2f} MB")
        
        # Compare with baseline
        baseline_path = os.path.join(args.input_dir, 'baseline_90d_daily.json')
        if os.path.exists(baseline_path):
            baseline_size = os.path.getsize(baseline_path) / 1024 / 1024
            compression_ratio = (1 - total_size / baseline_size) * 100
            print(f"📉 Compression ratio: {compression_ratio:.1f}%")
            print(f"   (from {baseline_size:.1f} MB to {total_size:.1f} MB)")
    else:
        print("\n❌ Transformation failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()