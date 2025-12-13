"""
Service d'agrégation de données columnar multi-compte
Merge meta_v1, agg_v1, summary_v1 de plusieurs comptes en un seul dataset

⚠️ TODO: Multi-currency aggregation bug (Dec 2025)
   - Currently sums spend_cents/purchase_value_cents across different currencies
   - MXN + USD + EUR = WRONG total (no conversion)
   - Impact: Only affects "Todas las cuentas" view for multi-currency users
   - Fix options: A) Group by currency, B) Convert to USD, C) Disable monetary totals
   - Low priority: Most users are mono-currency, per-account view works correctly
"""
from typing import List, Dict, Any
from datetime import datetime


def aggregate_columnar_data(
    accounts_data: List[Dict[str, Any]]
) -> tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """
    Agrège les données columnar de plusieurs comptes en un seul dataset

    Args:
        accounts_data: List of dicts with keys:
            - account_id: str
            - account_name: str
            - meta_v1: Dict
            - agg_v1: Dict
            - summary_v1: Dict

    Returns:
        (aggregated_meta_v1, aggregated_agg_v1, aggregated_summary_v1)

    Logic:
        - meta_v1.ads: CONCAT all ads
        - meta_v1.campaigns/adsets/accounts: MERGE dicts (union)
        - agg_v1.ads + values: CONCAT (keep order)
        - summary_v1.totals: SUM by period
    """
    if not accounts_data:
        # Return empty structures
        return _empty_aggregated()

    # Initialize aggregated structures
    aggregated_meta = {
        "version": 1,
        "metadata": {},
        "ads": [],
        "campaigns": {},
        "adsets": {},
        "accounts": {}
    }

    aggregated_agg = {
        "version": 1,
        "periods": ["3d", "7d", "14d", "30d", "90d"],
        "metrics": ["impressions", "clicks", "unique_link_clicks", "results", "purchases", "spend", "purchase_value", "reach", "cpm", "ctr"],
        "ads": [],
        "values": [],
        "scales": {"money": 100}
    }

    aggregated_summary = {
        "periods": ["3d", "7d", "14d", "30d", "90d"],
        "totals": {
            "3d": {"impr": 0, "clk": 0, "purch": 0, "spend_cents": 0, "purchase_value_cents": 0, "reach": 0},
            "7d": {"impr": 0, "clk": 0, "purch": 0, "spend_cents": 0, "purchase_value_cents": 0, "reach": 0},
            "14d": {"impr": 0, "clk": 0, "purch": 0, "spend_cents": 0, "purchase_value_cents": 0, "reach": 0},
            "30d": {"impr": 0, "clk": 0, "purch": 0, "spend_cents": 0, "purchase_value_cents": 0, "reach": 0},
            "90d": {"impr": 0, "clk": 0, "purch": 0, "spend_cents": 0, "purchase_value_cents": 0, "reach": 0}
        }
    }

    # Track latest metadata for global info
    latest_metadata = None

    # Aggregate each account
    for account_data in accounts_data:
        meta = account_data.get("meta_v1", {})
        agg = account_data.get("agg_v1", {})
        summary = account_data.get("summary_v1", {})

        # 1. Meta: CONCAT ads
        account_ads = meta.get("ads", [])
        aggregated_meta["ads"].extend(account_ads)

        # 2. Meta: MERGE campaigns/adsets/accounts dicts
        aggregated_meta["campaigns"].update(meta.get("campaigns", {}))
        aggregated_meta["adsets"].update(meta.get("adsets", {}))
        aggregated_meta["accounts"].update(meta.get("accounts", {}))

        # 3. Meta: Keep latest metadata (for reference_date, etc.)
        account_metadata = meta.get("metadata", {})
        if account_metadata:
            if not latest_metadata:
                latest_metadata = account_metadata.copy()
            else:
                # Use most recent data_max_date
                if account_metadata.get("data_max_date", "") > latest_metadata.get("data_max_date", ""):
                    latest_metadata = account_metadata.copy()

        # 4. Agg: CONCAT ads + values (keep order!)
        account_agg_ads = agg.get("ads", [])
        account_agg_values = agg.get("values", [])

        aggregated_agg["ads"].extend(account_agg_ads)
        aggregated_agg["values"].extend(account_agg_values)

        # 5. Summary: SUM totals by period
        summary_totals = summary.get("totals", {})
        for period in ["3d", "7d", "14d", "30d", "90d"]:
            period_data = summary_totals.get(period, {})
            if period_data:
                aggregated_summary["totals"][period]["impr"] += period_data.get("impr", 0)
                aggregated_summary["totals"][period]["clk"] += period_data.get("clk", 0)
                aggregated_summary["totals"][period]["purch"] += period_data.get("purch", 0)
                aggregated_summary["totals"][period]["spend_cents"] += period_data.get("spend_cents", 0)
                aggregated_summary["totals"][period]["purchase_value_cents"] += period_data.get("purchase_value_cents", 0)
                # Reach is non-additive, keep 0 for aggregated (no meaningful way to sum)

    # Set aggregated metadata
    if latest_metadata:
        aggregated_meta["metadata"] = latest_metadata.copy()
        # Override to indicate aggregated source
        aggregated_meta["metadata"]["source"] = "tenant_aggregated"
        aggregated_meta["metadata"]["pipeline"] = "backend_columnar_aggregator"
        aggregated_meta["metadata"]["aggregated_accounts_count"] = len(accounts_data)
        aggregated_meta["metadata"]["last_update"] = datetime.now().isoformat()

    return aggregated_meta, aggregated_agg, aggregated_summary


def _empty_aggregated() -> tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """Return empty but valid aggregated structures"""
    periods = ["3d", "7d", "14d", "30d", "90d"]

    meta_v1 = {
        "version": 1,
        "metadata": {
            "reference_date": datetime.now().date().isoformat(),
            "reference_hour": datetime.now().isoformat(),
            "buffer_hours": 0,
            "includes_today": False,
            "data_min_date": datetime.now().date().isoformat(),
            "data_max_date": datetime.now().date().isoformat(),
            "data_range_days": 0,
            "last_update": datetime.now().isoformat(),
            "source": "tenant_aggregated",
            "pipeline": "backend_columnar_aggregator",
            "aggregated_accounts_count": 0
        },
        "ads": [],
        "campaigns": {},
        "adsets": {},
        "accounts": {}
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
