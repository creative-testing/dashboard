"""
Service de refresh des données Meta Ads
Orchestre: fetch API → transform → storage
"""
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from ..services.meta_client import meta_client, MetaAPIError
from ..services import storage
from .. import models
from cryptography.fernet import Fernet
from ..config import settings

# Fernet pour déchiffrer les tokens
fernet = Fernet(settings.TOKEN_ENCRYPTION_KEY.encode())


class RefreshError(Exception):
    """Erreur lors du refresh des données"""
    pass


async def refresh_account_data(
    ad_account_id: str,
    tenant_id: UUID,
    db: Session
) -> Dict[str, Any]:
    """
    Refresh les données d'un ad account et génère les fichiers optimisés

    Args:
        ad_account_id: ID du compte (ex: "act_123456")
        tenant_id: ID du tenant (pour isolation)
        db: Session SQLAlchemy

    Returns:
        {
            "status": "success",
            "ad_account_id": str,
            "ads_fetched": int,
            "files_written": List[str],
            "refreshed_at": str (ISO)
        }

    Raises:
        RefreshError: Si erreur pendant le refresh
    """

    # 1. Vérifier que l'ad account appartient au tenant
    ad_account = db.execute(
        select(models.AdAccount).where(
            models.AdAccount.fb_account_id == ad_account_id,
            models.AdAccount.tenant_id == tenant_id
        )
    ).scalar_one_or_none()

    if not ad_account:
        raise RefreshError(f"Ad account {ad_account_id} not found for tenant {tenant_id}")

    # 2. Récupérer le token OAuth du tenant
    oauth_token = db.execute(
        select(models.OAuthToken).where(
            models.OAuthToken.tenant_id == tenant_id,
            models.OAuthToken.provider == "meta"
        )
    ).scalar_one_or_none()

    if not oauth_token:
        raise RefreshError(f"No OAuth token found for tenant {tenant_id}")

    # 3. Déchiffrer le token
    try:
        access_token = fernet.decrypt(oauth_token.access_token).decode()
    except Exception as e:
        raise RefreshError(f"Failed to decrypt access token: {e}")

    # 4. Fetch ads avec insights depuis Meta API
    try:
        ads_data = await _fetch_ads_with_insights(ad_account_id, access_token)
    except MetaAPIError as e:
        raise RefreshError(f"Meta API error: {e}")

    # 5. Transform en format optimisé
    meta_v1 = _transform_to_meta_v1(ads_data, ad_account_id)
    agg_v1 = _transform_to_agg_v1(ads_data)
    summary_v1 = _transform_to_summary_v1(ads_data)

    # 6. Écrire dans le storage
    files_written = []
    for filename, data in [
        ("meta_v1.json", meta_v1),
        ("agg_v1.json", agg_v1),
        ("summary_v1.json", summary_v1),
    ]:
        storage_key = f"tenants/{tenant_id}/accounts/{ad_account_id}/{filename}"
        try:
            storage.put_object(storage_key, json.dumps(data, indent=2).encode("utf-8"))
            files_written.append(filename)
        except storage.StorageError as e:
            raise RefreshError(f"Failed to write {filename}: {e}")

    # 7. Mettre à jour last_refresh_at
    ad_account.last_refresh_at = datetime.now(timezone.utc)
    db.commit()

    return {
        "status": "success",
        "ad_account_id": ad_account_id,
        "ads_fetched": len(ads_data),
        "files_written": files_written,
        "refreshed_at": ad_account.last_refresh_at.isoformat(),
    }


async def _fetch_ads_with_insights(
    ad_account_id: str,
    access_token: str
) -> list[Dict[str, Any]]:
    """
    Fetch ads avec insights depuis Meta API

    Returns:
        Liste d'ads avec leurs insights (impressions, clics, spend, etc.)
    """
    # Pour l'instant, on va chercher les 30 derniers jours
    # TODO: Adapter selon les besoins (90 jours comme dans le pipeline actuel)

    # Calculer la plage de dates: 30 jours, EXCLUDE TODAY (données partielles)
    today = datetime.now(timezone.utc).date()
    since = (today - timedelta(days=30)).isoformat()
    until = (today - timedelta(days=1)).isoformat()  # yesterday (INCLUDE_TODAY=0)

    # Endpoint: /{ad_account_id}/ads
    # Fields: Syntaxe simplifiée compatible Meta API
    # Note: insights est demandé comme field séparé, le time_range est passé explicitement
    fields = (
        "id,name,status,created_time,updated_time,"
        "creative{id,name,title,body,image_url,video_id,thumbnail_url},"
        "insights{date_start,date_stop,impressions,clicks,spend,cpc,cpm,ctr,reach,frequency,actions,action_values}"
    )

    # Call Meta API (on réutilise la logique de meta_client)
    ads_url = f"{meta_client.base_url}/{ad_account_id}/ads"
    proof = meta_client._generate_appsecret_proof(access_token)

    response = await meta_client._request_with_retry(
        "GET",
        ads_url,
        params={
            "access_token": access_token,
            "appsecret_proof": proof,
            "fields": fields,
            "limit": 500,  # Max par page
            "time_range": {"since": since, "until": until},  # Explicit date range, exclude today
        }
    )

    return response.get("data", [])


def _transform_to_meta_v1(ads_data: list[Dict[str, Any]], ad_account_id: str) -> Dict[str, Any]:
    """
    Transforme les ads en format meta_v1.json (structure columnar)

    Format minimal MVP pour dashboard:
    {
        "metadata": {...},
        "ads": [...],
        "data_min_date": "YYYY-MM-DD",
        "data_max_date": "YYYY-MM-DD"
    }
    """
    now = datetime.now(timezone.utc)

    # Extraire les dates min/max des insights
    all_dates = []
    for ad in ads_data:
        if "insights" in ad and "data" in ad["insights"]:
            for insight in ad["insights"]["data"]:
                if "date_start" in insight:
                    all_dates.append(insight["date_start"])
                if "date_stop" in insight:
                    all_dates.append(insight["date_stop"])

    data_min_date = min(all_dates) if all_dates else now.strftime("%Y-%m-%d")
    data_max_date = max(all_dates) if all_dates else now.strftime("%Y-%m-%d")

    # Structure des ads
    ads_list = []
    for ad in ads_data:
        # Agréger les insights (somme sur la période)
        total_impressions = 0
        total_clicks = 0
        total_spend = 0.0

        if "insights" in ad and "data" in ad["insights"]:
            for insight in ad["insights"]["data"]:
                total_impressions += int(insight.get("impressions", 0))
                total_clicks += int(insight.get("clicks", 0))
                total_spend += float(insight.get("spend", 0))

        # Creative info
        creative = ad.get("creative", {})

        ads_list.append({
            "id": ad.get("id"),
            "name": ad.get("name"),
            "status": ad.get("status"),
            "creative_id": creative.get("id"),
            "creative_name": creative.get("name"),
            "creative_title": creative.get("title"),
            "creative_body": creative.get("body"),
            "creative_image_url": creative.get("image_url"),
            "impressions": total_impressions,
            "clicks": total_clicks,
            "spend": total_spend,
            "ctr": round((total_clicks / total_impressions * 100), 2) if total_impressions > 0 else 0,
            "cpc": round((total_spend / total_clicks), 2) if total_clicks > 0 else 0,
        })

    return {
        "metadata": {
            "account_id": ad_account_id,
            "generated_at": now.isoformat(),
            "version": "v1",
            "total_ads": len(ads_list),
        },
        "data_min_date": data_min_date,
        "data_max_date": data_max_date,
        "ads": ads_list,
    }


def _transform_to_agg_v1(ads_data: list[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Transforme en format agg_v1.json (agrégations globales)

    Format MVP:
    {
        "total_impressions": int,
        "total_clicks": int,
        "total_spend": float,
        "avg_ctr": float,
        "avg_cpc": float
    }
    """
    total_impressions = 0
    total_clicks = 0
    total_spend = 0.0

    for ad in ads_data:
        if "insights" in ad and "data" in ad["insights"]:
            for insight in ad["insights"]["data"]:
                total_impressions += int(insight.get("impressions", 0))
                total_clicks += int(insight.get("clicks", 0))
                total_spend += float(insight.get("spend", 0))

    return {
        "total_impressions": total_impressions,
        "total_clicks": total_clicks,
        "total_spend": round(total_spend, 2),
        "avg_ctr": round((total_clicks / total_impressions * 100), 2) if total_impressions > 0 else 0,
        "avg_cpc": round((total_spend / total_clicks), 2) if total_clicks > 0 else 0,
    }


def _transform_to_summary_v1(ads_data: list[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Transforme en format summary_v1.json (résumé rapide)

    Format MVP:
    {
        "total_ads": int,
        "active_ads": int,
        "paused_ads": int,
        "total_spend": float
    }
    """
    total_ads = len(ads_data)
    active_ads = sum(1 for ad in ads_data if ad.get("status") == "ACTIVE")
    paused_ads = sum(1 for ad in ads_data if ad.get("status") == "PAUSED")

    total_spend = 0.0
    for ad in ads_data:
        if "insights" in ad and "data" in ad["insights"]:
            for insight in ad["insights"]["data"]:
                total_spend += float(insight.get("spend", 0))

    return {
        "total_ads": total_ads,
        "active_ads": active_ads,
        "paused_ads": paused_ads,
        "total_spend": round(total_spend, 2),
    }
