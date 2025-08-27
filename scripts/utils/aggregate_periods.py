#!/usr/bin/env python3
"""
Aggregate 90d daily baseline into period-level datasets (3/7/14/30/90 days).

Input: data/current/baseline_90d_daily.json
Output: data/current/hybrid_data_{period}d.json with same shape as dashboards expect.
"""
import json
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, Any


def _parse_date(s: str) -> datetime:
    for fmt in ('%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S'):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            continue
    raise ValueError(f"Unrecognized date format: {s}")


def _date_str(dt: datetime) -> str:
    return dt.strftime('%Y-%m-%d')


def aggregate_from_baseline(baseline_path: str, period_days: int, reference_date: str) -> Dict[str, Any]:
    with open(baseline_path, 'r', encoding='utf-8') as f:
        base = json.load(f)
    daily_rows = base.get('daily_ads', [])

    ref = _parse_date(reference_date)
    end_date = ref
    start_date = ref - timedelta(days=period_days - 1)
    start_s, end_s = _date_str(start_date), _date_str(end_date)

    # aggregate by ad_id within [start_s, end_s]
    ad_bucket: Dict[str, Dict[str, Any]] = {}

    def add_metrics(dst: Dict[str, Any], src: Dict[str, Any]):
        dst['spend'] = dst.get('spend', 0.0) + float(src.get('spend', 0) or 0)
        dst['impressions'] = dst.get('impressions', 0) + int(src.get('impressions', 0) or 0)
        dst['clicks'] = dst.get('clicks', 0) + int(src.get('clicks', 0) or 0)
        dst['reach'] = dst.get('reach', 0) + int(src.get('reach', 0) or 0)
        dst['frequency'] = dst.get('frequency', 0.0) + float(src.get('frequency', 0) or 0)
        # actions and action_values: accumulate purchase and value
        for a in src.get('actions', []) or []:
            if a.get('action_type') in ('purchase', 'omni_purchase'):
                dst['purchases'] = dst.get('purchases', 0) + int(a.get('value', 0) or 0)
        for av in src.get('action_values', []) or []:
            if av.get('action_type') in ('purchase', 'omni_purchase'):
                dst['purchase_value'] = dst.get('purchase_value', 0.0) + float(av.get('value', 0) or 0)

    for row in daily_rows:
        d = row.get('date') or row.get('date_start') or ''
        if not d:
            continue
        # ensure date string
        if len(d) > 10:
            try:
                d = d[:10]
            except Exception:
                continue
        if d < start_s or d > end_s:
            continue
        ad_id = row.get('ad_id')
        if not ad_id:
            continue
        if ad_id not in ad_bucket:
            ad_bucket[ad_id] = {
                'account_name': row.get('account_name', ''),
                'ad_name': row.get('ad_name', ''),
                'ad_id': ad_id,
                'campaign_name': row.get('campaign_name', ''),
                'format': row.get('format', 'UNKNOWN'),
                'spend': 0.0,
                'impressions': 0,
                'clicks': 0,
                'ctr': 0.0,  # computed later
                'cpm': 0.0,  # computed later
                'reach': 0,
                'frequency': 0.0,
                'purchases': 0,
                'purchase_value': 0.0,
                'roas': 0.0,  # computed later
                'media_url': row.get('media_url', ''),
            }
        add_metrics(ad_bucket[ad_id], row)

    # finalize derived metrics
    ads = []
    for ad in ad_bucket.values():
        impr = ad.get('impressions', 0)
        spend = ad.get('spend', 0.0)
        clicks = ad.get('clicks', 0)
        ad['ctr'] = (clicks / impr * 100.0) if impr > 0 else 0.0
        ad['cpm'] = (spend / impr * 1000.0) if impr > 0 else 0.0
        pv = ad.get('purchase_value', 0.0)
        ad['roas'] = (pv / spend) if spend > 0 else 0.0
        ads.append(ad)

    # optional: format distribution
    fmt = defaultdict(int)
    for ad in ads:
        fmt[ad.get('format', 'UNKNOWN')] += 1

    out = {
        'metadata': {
            'timestamp': datetime.now().isoformat(),
            'reference_date': reference_date,
            'period_days': period_days,
            'date_range': f'{start_s} to {end_s}',
            'method': 'baseline_aggregate',
            'total_ads': len(ads),
        },
        'format_distribution': dict(fmt),
        'ads': ads,
    }
    return out


__all__ = ['aggregate_from_baseline']

