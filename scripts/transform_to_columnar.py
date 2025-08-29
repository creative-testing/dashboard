#!/usr/bin/env python3
"""
Transforme les données existantes vers la structure columnaire optimisée GPT-5
Génère: meta_v1.json, agg_v1.json, summary_v1.json, ts_90d_v1.json.gz
"""
import json
import gzip
import os
from collections import defaultdict
from datetime import datetime
import sys

def load_json(path):
    """Load JSON file"""
    print(f"  Loading {path}...")
    with open(path, 'r') as f:
        return json.load(f)

def save_json(data, path, minify=True):
    """Save JSON file"""
    with open(path, 'w') as f:
        if minify:
            json.dump(data, f, separators=(',', ':'))
        else:
            json.dump(data, f, indent=2)
    size_mb = os.path.getsize(path) / 1024 / 1024
    print(f"  ✓ Saved {path} ({size_mb:.1f} MB)")

def save_json_gz(data, path):
    """Save gzipped JSON"""
    json_str = json.dumps(data, separators=(',', ':'))
    with gzip.open(path, 'wt', encoding='utf-8', compresslevel=9) as f:
        f.write(json_str)
    size_mb = os.path.getsize(path) / 1024 / 1024
    print(f"  ✓ Saved {path} ({size_mb:.1f} MB)")

def transform_data(input_dir, output_dir):
    """Transform data to columnar format"""
    
    print("🚀 Starting transformation to columnar format...")
    os.makedirs(output_dir, exist_ok=True)
    
    # Load all period files
    periods_data = {}
    period_configs = [
        ("3d", 3),
        ("7d", 7),
        ("14d", 14),
        ("30d", 30),
        ("90d", 90)
    ]
    
    for period_name, days in period_configs:
        file_path = f"{input_dir}/hybrid_data_{period_name}.json"
        if os.path.exists(file_path):
            periods_data[period_name] = load_json(file_path)
    
    # Also load and compress prev_week if exists
    prev_week_data = None
    prev_week_path = f"{input_dir}/hybrid_data_prev_week.json"
    if os.path.exists(prev_week_path):
        print(f"  Loading prev_week data...")
        prev_week_data = load_json(prev_week_path)
    
    if not periods_data:
        print("❌ No data files found!")
        return False
    
    print(f"\n📊 Processing {len(periods_data)} periods...")
    
    # 1. Build unique ads index and metadata
    all_ads = {}
    campaigns = {}
    adsets = {}
    accounts = {}
    
    # Aggregate by ad_id for each period
    aggregated_by_period = {}
    
    for period_name, data in periods_data.items():
        print(f"\n  Processing {period_name}...")
        ads_in_period = data.get('ads', [])
        print(f"    Found {len(ads_in_period)} rows")
        
        # Aggregate by ad_id
        aggregated = defaultdict(lambda: {
            'impressions': 0,
            'clicks': 0,
            'spend': 0.0,
            'purchases': 0,
            'purchase_value': 0.0,
            'reach': 0,
            'dates_seen': set()
        })
        
        for ad in ads_in_period:
            ad_id = ad['ad_id']
            
            # Store metadata (only once per ad)
            if ad_id not in all_ads:
                all_ads[ad_id] = {
                    'id': ad_id,
                    'name': ad.get('ad_name', ''),
                    'cid': ad.get('campaign_id', ''),
                    'aid': ad.get('adset_id', ''),
                    'acc': ad.get('account_id', ''),
                    'format': ad.get('format', 'unknown'),
                    'status': ad.get('effective_status', 'unknown'),
                    'media': ad.get('media_url', ''),
                    'ct': ad.get('created_time', '')
                }
                
                # Store campaign/adset/account names
                if ad.get('campaign_id'):
                    campaigns[ad['campaign_id']] = {'name': ad.get('campaign_name', '')}
                if ad.get('adset_id'):
                    adsets[ad['adset_id']] = {'name': ad.get('adset_name', '')}
                if ad.get('account_id'):
                    accounts[ad['account_id']] = {'name': ad.get('account_name', '')}
            
            # Aggregate metrics
            aggregated[ad_id]['impressions'] += int(ad.get('impressions', 0))
            aggregated[ad_id]['clicks'] += int(ad.get('clicks', 0))
            aggregated[ad_id]['spend'] += float(ad.get('spend', 0))
            aggregated[ad_id]['purchases'] += int(ad.get('purchases', 0))
            aggregated[ad_id]['purchase_value'] += float(ad.get('purchase_value', 0))
            aggregated[ad_id]['reach'] += int(ad.get('reach', 0))
            
            if ad.get('date_start'):
                aggregated[ad_id]['dates_seen'].add(ad['date_start'])
        
        aggregated_by_period[period_name] = dict(aggregated)
        unique_ads = len(aggregated)
        print(f"    Aggregated to {unique_ads} unique ads")
    
    # Sort ads for stable ordering
    sorted_ad_ids = sorted(all_ads.keys())
    ad_index_map = {ad_id: idx for idx, ad_id in enumerate(sorted_ad_ids)}
    
    print(f"\n📈 Building columnar structure for {len(sorted_ad_ids)} unique ads...")
    
    # 2. Build agg_v1.json (columnar aggregates)
    periods = ["3d", "7d", "14d", "30d", "90d"]
    metrics = ["impr", "clk", "purch", "spend_cents", "purchase_value_cents", "reach"]
    values = []
    
    for ad_id in sorted_ad_ids:
        for period in periods:
            if period in aggregated_by_period and ad_id in aggregated_by_period[period]:
                agg = aggregated_by_period[period][ad_id]
                values.extend([
                    agg['impressions'],
                    agg['clicks'],
                    agg['purchases'],
                    int(agg['spend'] * 100),  # Convert to cents
                    int(agg['purchase_value'] * 100),  # Convert to cents
                    agg['reach']
                ])
            else:
                # No data for this period
                values.extend([0, 0, 0, 0, 0, 0])
    
    agg_data = {
        "version": 1,
        "generated_at": datetime.now().isoformat(),
        "periods": periods,
        "metrics": metrics,
        "ads": sorted_ad_ids,
        "values": values,
        "scales": {"money": 100}
    }
    
    # 3. Build meta_v1.json
    meta_ads = []
    for idx, ad_id in enumerate(sorted_ad_ids):
        ad = all_ads[ad_id]
        meta_ads.append({
            "i": idx,
            "id": ad['id'],
            "name": ad['name'][:100] if ad['name'] else '',  # Truncate long names
            "cid": ad['cid'],
            "aid": ad['aid'],
            "acc": ad['acc'],
            "format": ad['format'],
            "status": ad['status'],
            "media": ad['media'][:200] if ad['media'] else '',  # Truncate long URLs
            "ct": ad['ct']
        })
    
    meta_data = {
        "version": 1,
        "ads": meta_ads,
        "campaigns": campaigns,
        "adsets": adsets,
        "accounts": accounts
    }
    
    # 4. Build summary_v1.json
    summary_totals = {}
    for period in periods:
        if period in aggregated_by_period:
            total_impr = sum(a['impressions'] for a in aggregated_by_period[period].values())
            total_clk = sum(a['clicks'] for a in aggregated_by_period[period].values())
            total_purch = sum(a['purchases'] for a in aggregated_by_period[period].values())
            total_spend = sum(a['spend'] for a in aggregated_by_period[period].values())
            total_pval = sum(a['purchase_value'] for a in aggregated_by_period[period].values())
            total_reach = sum(a['reach'] for a in aggregated_by_period[period].values())
            
            summary_totals[period] = {
                "impr": total_impr,
                "clk": total_clk,
                "purch": total_purch,
                "spend_cents": int(total_spend * 100),
                "purchase_value_cents": int(total_pval * 100),
                "reach": total_reach
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
    
    # 5. Build manifest.json
    manifest_data = {
        "version": datetime.now().isoformat(),
        "ads_count": len(sorted_ad_ids),
        "periods": periods,
        "shards": {
            "meta": {"path": "meta_v1.json"},
            "agg": {"path": "agg_v1.json"},
            "summary": {"path": "summary_v1.json"}
        }
    }
    
    # Save all files
    print("\n💾 Saving optimized files...")
    save_json(meta_data, f"{output_dir}/meta_v1.json")
    save_json(agg_data, f"{output_dir}/agg_v1.json")
    save_json(summary_data, f"{output_dir}/summary_v1.json")
    save_json(manifest_data, f"{output_dir}/manifest.json")
    
    # Compress prev_week if available
    if prev_week_data:
        print("\n🗜️  Compressing previous week data...")
        # Aggregate prev_week by ad_id
        prev_week_aggregated = defaultdict(lambda: {
            'impressions': 0,
            'clicks': 0,
            'spend': 0.0,
            'purchases': 0,
            'purchase_value': 0.0,
            'reach': 0
        })
        
        for ad in prev_week_data.get('ads', []):
            ad_id = ad['ad_id']
            prev_week_aggregated[ad_id]['impressions'] += int(ad.get('impressions', 0))
            prev_week_aggregated[ad_id]['clicks'] += int(ad.get('clicks', 0))
            prev_week_aggregated[ad_id]['spend'] += float(ad.get('spend', 0))
            prev_week_aggregated[ad_id]['purchases'] += int(ad.get('purchases', 0))
            prev_week_aggregated[ad_id]['purchase_value'] += float(ad.get('purchase_value', 0))
            prev_week_aggregated[ad_id]['reach'] += int(ad.get('reach', 0))
            
            # Keep first occurrence metadata
            if 'ad_name' not in prev_week_aggregated[ad_id]:
                prev_week_aggregated[ad_id].update({
                    'ad_id': ad_id,
                    'ad_name': ad.get('ad_name', ''),
                    'campaign_name': ad.get('campaign_name', ''),
                    'campaign_id': ad.get('campaign_id', ''),
                    'adset_name': ad.get('adset_name', ''),
                    'adset_id': ad.get('adset_id', ''),
                    'account_name': ad.get('account_name', ''),
                    'account_id': ad.get('account_id', ''),
                    'effective_status': ad.get('effective_status', ''),
                    'format': ad.get('format', ''),
                    'media_url': ad.get('media_url', ''),
                    'created_time': ad.get('created_time', '')
                })
        
        # Convert back to list format
        prev_week_compressed = {
            'period': 'prev_week',
            'ads': list(prev_week_aggregated.values())
        }
        
        save_json(prev_week_compressed, f"{output_dir}/prev_week_compressed.json")
        
        # Show compression stats
        original_size = os.path.getsize(prev_week_path) / 1024 / 1024
        compressed_size = os.path.getsize(f"{output_dir}/prev_week_compressed.json") / 1024 / 1024
        print(f"  ✓ Previous week: {original_size:.1f}MB → {compressed_size:.1f}MB ({(1-compressed_size/original_size)*100:.1f}% reduction)")
    
    # Calculate space savings
    print("\n📊 Transformation complete!")
    print(f"  • Unique ads: {len(sorted_ad_ids)}")
    print(f"  • Periods: {len(periods)}")
    print(f"  • Total values: {len(values)} numbers")
    
    # Show file sizes
    total_size = 0
    for file in ['meta_v1.json', 'agg_v1.json', 'summary_v1.json', 'manifest.json']:
        path = f"{output_dir}/{file}"
        if os.path.exists(path):
            size = os.path.getsize(path) / 1024 / 1024
            total_size += size
    
    print(f"\n✅ Total size: {total_size:.1f} MB (from ~550 MB original)")
    print(f"   Reduction: {(1 - total_size/550) * 100:.1f}%")
    
    return True

if __name__ == "__main__":
    # Use backup data as source
    input_dir = "data/backup_emergency_20250828_174343"
    output_dir = "data/optimized"
    
    if not os.path.exists(input_dir):
        print(f"❌ Input directory not found: {input_dir}")
        sys.exit(1)
    
    success = transform_data(input_dir, output_dir)
    sys.exit(0 if success else 1)