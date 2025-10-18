"""
Transform daily Meta Ads insights to columnar format
Port of scripts/transform_to_columnar.py for backend API

CRITICAL: Must produce EXACT same format as production pipeline
"""
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Any


def _process_purchases(ad: Dict[str, Any]) -> tuple[int, float]:
    """
    Extract purchases and purchase_value from actions/conversions
    Priority: omni_purchase > purchase > offsite_conversion.fb_pixel_purchase

    Returns:
        (purchases, purchase_value)
    """
    PURCHASE_KEYS = [
        'omni_purchase',
        'purchase',
        'offsite_conversion.fb_pixel_purchase',
        'onsite_conversion.purchase',
        'onsite_web_purchase'
    ]

    def _map_values(items):
        """Create dict of action_type -> value"""
        return {i.get('action_type', ''): float(i.get('value', 0) or 0) for i in (items or [])}

    # Priority: conversions > actions
    conv_map = _map_values(ad.get('conversions', []))
    conv_val_map = _map_values(ad.get('conversion_values', []))

    act_map = _map_values(ad.get('actions', [])) if not conv_map else {}
    act_val_map = _map_values(ad.get('action_values', [])) if not conv_val_map else {}

    def _pick_first(mapping, keys):
        """Pick first value found in priority order"""
        for k in keys:
            if k in mapping and mapping[k] > 0:
                return mapping[k]
        return 0.0

    purchases = _pick_first(conv_map or act_map, PURCHASE_KEYS)
    purchase_value = _pick_first(conv_val_map or act_val_map, PURCHASE_KEYS)

    return int(round(purchases)), float(purchase_value)


def _process_leads(ad: Dict[str, Any]) -> int:
    """
    Extract leads (results) from actions/conversions

    Returns:
        Number of leads
    """
    LEAD_KEYS = ['lead', 'offsite_conversion.fb_lead']

    def _sum(items, keys):
        s = 0.0
        for k in keys:
            for i in (items or []):
                if i.get('action_type') == k:
                    try:
                        s += float(i.get('value', 0) or 0)
                    except:
                        pass
        return s

    # Priority: conversions > actions
    conv = _sum(ad.get('conversions', []), LEAD_KEYS)
    acts = _sum(ad.get('actions', []), LEAD_KEYS) if conv == 0 else 0.0

    leads = conv if conv > 0 else acts
    return int(round(leads))


def _process_unique_link_clicks(ad: Dict[str, Any]) -> int:
    """
    Extract unique_link_clicks from unique_outbound_clicks
    Format: [{'action_type': 'outbound_click', 'value': '17'}]

    Returns:
        Number of unique link clicks
    """
    outbound_total = 0
    outbound_data = ad.get('unique_outbound_clicks', [])
    if isinstance(outbound_data, list):
        for item in outbound_data:
            if isinstance(item, dict) and item.get('action_type') == 'outbound_click':
                try:
                    outbound_total += int(item.get('value', 0))
                except:
                    pass
    return outbound_total


def transform_to_columnar(
    daily_ads: List[Dict[str, Any]],
    reference_date: str,
    ad_account_id: str,
    account_name: str = None
) -> tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """
    Transform daily insights to columnar format

    Args:
        daily_ads: List of daily ad insights from Meta API
        reference_date: Reference date (YYYY-MM-DD)
        ad_account_id: Account ID for metadata
        account_name: Account name for display (defaults to ID if not provided)

    Returns:
        (meta_v1, agg_v1, summary_v1)
    """

    # Default account_name to ID if not provided
    if account_name is None:
        account_name = ad_account_id

    if not daily_ads:
        # Return empty but valid structures
        return _empty_structures(reference_date, ad_account_id, account_name)

    # Sort by date DESC to keep newest metadata (fresh URLs)
    daily_ads.sort(key=lambda ad: ad.get('date_start', ''), reverse=True)

    # Determine data range
    all_dates = [ad['date_start'] for ad in daily_ads if ad.get('date_start')]
    if not all_dates:
        return _empty_structures(reference_date, ad_account_id)

    min_date = min(all_dates)
    max_date = max(all_dates)
    min_dt = datetime.strptime(min_date, '%Y-%m-%d')
    max_dt = datetime.strptime(max_date, '%Y-%m-%d')
    data_range_days = (max_dt - min_dt).days + 1

    # Define periods
    periods = ['3d', '7d', '14d', '30d', '90d']

    # Calculate cutoff dates for each period
    reference_dt = datetime.strptime(reference_date, '%Y-%m-%d')
    cutoff_dates = {}
    for period in periods:
        days = int(period.replace('d', ''))
        if days > data_range_days:
            cutoff_dates[period] = min_date
        else:
            cutoff_dates[period] = (reference_dt - timedelta(days=days-1)).strftime('%Y-%m-%d')

    # Aggregate by period and ad_id
    aggregated_by_period = defaultdict(lambda: defaultdict(lambda: {
        'impressions': 0,
        'clicks': 0,
        'unique_link_clicks': 0,
        'results': 0,
        'spend': 0.0,
        'purchases': 0,
        'purchase_value': 0.0,
        'reach': 0  # Will store max daily reach
    }))

    # Process all ads
    for ad in daily_ads:
        ad_id = ad.get('ad_id')
        if not ad_id:
            continue

        ad_date = ad.get('date_start')
        if not ad_date:
            continue

        # Process special metrics
        purchases, purchase_value = _process_purchases(ad)
        results = _process_leads(ad)
        unique_link_clicks = _process_unique_link_clicks(ad)

        # Aggregate for each period
        for period in periods:
            if ad_date >= cutoff_dates[period]:
                agg = aggregated_by_period[period][ad_id]

                # Aggregate metrics
                agg['impressions'] += int(ad.get('impressions', 0) or 0)
                agg['clicks'] += int(ad.get('clicks', 0) or 0)
                agg['unique_link_clicks'] += unique_link_clicks
                agg['results'] += results
                agg['spend'] += float(ad.get('spend', 0) or 0)
                agg['purchases'] += purchases
                agg['purchase_value'] += purchase_value

                # Reach: keep MAX daily (non-additive)
                try:
                    r = int(ad.get('reach', 0) or 0)
                    if r > agg['reach']:
                        agg['reach'] = r
                except:
                    pass

                # Weighted averages for CPM/CTR
                impressions = int(ad.get('impressions', 0) or 0)
                if impressions > 0:
                    if 'cpm_weighted' not in agg:
                        agg['cpm_weighted'] = 0
                        agg['ctr_weighted'] = 0
                        agg['total_impressions_weight'] = 0
                    agg['cpm_weighted'] += float(ad.get('cpm', 0) or 0) * impressions
                    agg['ctr_weighted'] += float(ad.get('ctr', 0) or 0) * impressions
                    agg['total_impressions_weight'] += impressions

                # Keep first occurrence metadata (newest due to DESC sort)
                if 'ad_name' not in agg:
                    agg['ad_name'] = ad.get('ad_name', '')
                    agg['campaign_name'] = ad.get('campaign_name', '')
                    agg['campaign_id'] = ad.get('campaign_id', '')
                    agg['adset_name'] = ad.get('adset_name', '')
                    agg['adset_id'] = ad.get('adset_id', '')
                    agg['account_name'] = account_name  # Use real account name from DB
                    agg['account_id'] = ad_account_id
                    agg['created_time'] = ad.get('created_time', '')
                    # Status and format will be enriched later if needed
                    agg['status'] = 'UNKNOWN'
                    agg['effective_status'] = 'UNKNOWN'
                    agg['format'] = 'UNKNOWN'
                    agg['media_url'] = ''

    # Build columnar structures
    # Use largest period (90d) as base to include all ads
    base_period = periods[-1]
    base_ads = aggregated_by_period[base_period]

    # Sort by spend DESC for better compression
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

        # Add values for each period (flattened)
        for period in periods:
            period_data = aggregated_by_period[period].get(ad_id, {})

            # Calculate weighted averages for CPM/CTR
            total_weight = period_data.get('total_impressions_weight', 0)
            cpm = 0
            ctr = 0
            if total_weight > 0:
                cpm = period_data.get('cpm_weighted', 0) / total_weight
                ctr = period_data.get('ctr_weighted', 0) / total_weight

            values.extend([
                period_data.get('impressions', 0),
                period_data.get('clicks', 0),
                period_data.get('unique_link_clicks', 0),
                period_data.get('results', 0),
                period_data.get('purchases', 0),
                int(period_data.get('spend', 0) * 100),  # Store as cents
                int(period_data.get('purchase_value', 0) * 100),  # Store as cents
                period_data.get('reach', 0),
                int(cpm * 100),  # Store CPM * 100
                int(ctr * 100)   # Store CTR * 100
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
            "media": ad_data.get('media_url', ''),
            "ct": ad_data.get('created_time', '')
        })

    # Build output files

    # 1. agg_v1.json - Columnar metrics data
    agg_v1 = {
        "version": 1,
        "periods": periods,
        "metrics": ["impressions", "clicks", "unique_link_clicks", "results", "purchases", "spend", "purchase_value", "reach", "cpm", "ctr"],
        "ads": ad_ids,
        "values": values,
        "scales": {"money": 100}  # Cents to dollars
    }

    # 2. meta_v1.json - Entity metadata
    meta_v1 = {
        "version": 1,
        "metadata": {
            "reference_date": reference_date,
            "reference_hour": datetime.now().isoformat(),
            "buffer_hours": 0,  # Backend doesn't use buffer
            "includes_today": False,  # Backend excludes today by default
            "data_min_date": min_date,
            "data_max_date": max_date,
            "data_range_days": data_range_days,
            "last_update": datetime.now().isoformat(),
            "source": "meta_api_insights",
            "pipeline": "backend_columnar_transform"
        },
        "ads": meta_ads,
        "campaigns": campaigns,
        "adsets": adsets,
        "accounts": accounts
    }

    # 3. summary_v1.json - Period totals
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
                "reach": 0  # Reach is non-additive
            }
        else:
            summary_totals[period] = {
                "impr": 0, "clk": 0, "purch": 0,
                "spend_cents": 0, "purchase_value_cents": 0, "reach": 0
            }

    summary_v1 = {
        "periods": periods,
        "totals": summary_totals
    }

    return meta_v1, agg_v1, summary_v1


def _empty_structures(reference_date: str, ad_account_id: str, account_name: str = None) -> tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """
    Return empty but valid structures when no data
    Prevents dashboard crashes with 0 ads
    """
    if account_name is None:
        account_name = ad_account_id

    periods = ['3d', '7d', '14d', '30d', '90d']

    meta_v1 = {
        "version": 1,
        "metadata": {
            "reference_date": reference_date,
            "reference_hour": datetime.now().isoformat(),
            "buffer_hours": 0,
            "includes_today": False,
            "data_min_date": reference_date,
            "data_max_date": reference_date,
            "data_range_days": 0,
            "last_update": datetime.now().isoformat(),
            "source": "meta_api_insights",
            "pipeline": "backend_columnar_transform"
        },
        "ads": [],
        "campaigns": {},
        "adsets": {},
        "accounts": {ad_account_id: {"name": account_name}}
    }

    agg_v1 = {
        "version": 1,
        "periods": periods,
        "metrics": ["impressions", "clicks", "unique_link_clicks", "results", "purchases", "spend", "purchase_value", "reach", "cpm", "ctr"],
        "ads": [],
        "values": [],
        "scales": {"money": 100}
    }

    summary_totals = {}
    for period in periods:
        summary_totals[period] = {
            "impr": 0, "clk": 0, "purch": 0,
            "spend_cents": 0, "purchase_value_cents": 0, "reach": 0
        }

    summary_v1 = {
        "periods": periods,
        "totals": summary_totals
    }

    return meta_v1, agg_v1, summary_v1


def validate_columnar_format(meta_v1: Dict, agg_v1: Dict, summary_v1: Dict) -> List[str]:
    """
    Validate columnar format integrity

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    # Check agg_v1 structure
    if 'periods' not in agg_v1 or agg_v1['periods'] != ['3d', '7d', '14d', '30d', '90d']:
        errors.append("agg_v1.periods must be ['3d', '7d', '14d', '30d', '90d']")

    if 'scales' not in agg_v1 or agg_v1['scales'].get('money') != 100:
        errors.append("agg_v1.scales.money must be 100")

    # Check values array length
    expected_metrics = 10  # impressions, clicks, unique_link_clicks, results, purchases, spend, purchase_value, reach, cpm, ctr
    expected_periods = 5   # 3d, 7d, 14d, 30d, 90d
    expected_length = len(agg_v1.get('ads', [])) * expected_periods * expected_metrics

    if len(agg_v1.get('values', [])) != expected_length:
        errors.append(f"agg_v1.values length mismatch: expected {expected_length}, got {len(agg_v1.get('values', []))}")

    # Check meta_v1 ads count matches agg_v1
    if len(meta_v1.get('ads', [])) != len(agg_v1.get('ads', [])):
        errors.append(f"meta_v1.ads count ({len(meta_v1.get('ads', []))}) != agg_v1.ads count ({len(agg_v1.get('ads', []))})")

    return errors
