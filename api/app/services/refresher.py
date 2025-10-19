"""
Service de refresh des données Meta Ads
Orchestre: fetch API → transform → storage

IMPORTANT: Produces columnar format matching production pipeline
"""
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import select

from ..services.meta_client import meta_client, MetaAPIError
from ..services import storage
from ..services.columnar_transform import transform_to_columnar, validate_columnar_format
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

    IMPORTANT: Generates columnar format (meta_v1, agg_v1, summary_v1)
    matching production pipeline for dashboard compatibility

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

    # 4. Calculer la plage de dates
    # Par défaut: 30 derniers jours, EXCLUDE TODAY (données partielles)
    # TODO: Configurable par tenant (30d, 90d, etc.)
    today = datetime.now(timezone.utc).date()
    since_date = (today - timedelta(days=30)).isoformat()
    until_date = (today - timedelta(days=1)).isoformat()  # Yesterday
    reference_date = until_date  # Reference date = last day of data

    # 5. Fetch daily insights depuis Meta API
    try:
        daily_insights = await meta_client.get_insights_daily(
            ad_account_id=ad_account_id,
            access_token=access_token,
            since_date=since_date,
            until_date=until_date,
            limit=500
        )
    except MetaAPIError as e:
        raise RefreshError(f"Meta API error: {e}")

    # 5b. Enrich with creatives (format, media_url, status)
    # CRITICAL: Parité avec ancien pipeline (fetch_with_smart_limits.py)
    try:
        print(f"🎨 Enriching {len(daily_insights)} insights with creatives...")
        if daily_insights:
            print(f"   Sample insight keys: {list(daily_insights[0].keys())[:10]}")

        daily_insights = await meta_client.enrich_ads_with_creatives(
            ads=daily_insights,
            access_token=access_token
        )
        print(f"✅ Enrichment complete")
    except Exception as e:
        # Enrichment failure is non-fatal - continue with UNKNOWN formats
        print(f"⚠️ Enrichment failed: {e}")
        import traceback
        traceback.print_exc()

    # 6. Transform en format columnar
    try:
        meta_v1, agg_v1, summary_v1 = transform_to_columnar(
            daily_ads=daily_insights,
            reference_date=reference_date,
            ad_account_id=ad_account_id,
            account_name=ad_account.name  # Pass real account name from DB
        )
    except Exception as e:
        raise RefreshError(f"Transform error: {e}")

    # 7. Valider le format
    validation_errors = validate_columnar_format(meta_v1, agg_v1, summary_v1)
    if validation_errors:
        raise RefreshError(f"Validation failed: {'; '.join(validation_errors)}")

    # 8. Écrire dans le storage
    files_written = []
    base_path = f"tenants/{tenant_id}/accounts/{ad_account_id}/data/optimized"

    for filename, data in [
        ("meta_v1.json", meta_v1),
        ("agg_v1.json", agg_v1),
        ("summary_v1.json", summary_v1),
    ]:
        storage_key = f"{base_path}/{filename}"
        try:
            # Use compact JSON (no indent) for production
            storage.put_object(storage_key, json.dumps(data, separators=(',', ':')).encode("utf-8"))
            files_written.append(filename)
        except storage.StorageError as e:
            raise RefreshError(f"Failed to write {filename}: {e}")

    # 9. Écrire manifest.json
    manifest = {
        "version": datetime.now(timezone.utc).isoformat(),
        "ads_count": len(agg_v1.get('ads', [])),
        "periods": agg_v1.get('periods', []),
        "shards": {
            "meta": {"path": "meta_v1.json"},
            "agg": {"path": "agg_v1.json"},
            "summary": {"path": "summary_v1.json"}
        }
    }
    try:
        storage.put_object(
            f"{base_path}/manifest.json",
            json.dumps(manifest, separators=(',', ':')).encode("utf-8")
        )
        files_written.append("manifest.json")
    except storage.StorageError as e:
        raise RefreshError(f"Failed to write manifest.json: {e}")

    # 10. Mettre à jour last_refresh_at
    ad_account.last_refresh_at = datetime.now(timezone.utc)
    db.commit()

    return {
        "status": "success",
        "ad_account_id": ad_account_id,
        "daily_rows_fetched": len(daily_insights),
        "unique_ads": len(agg_v1.get('ads', [])),
        "files_written": files_written,
        "refreshed_at": ad_account.last_refresh_at.isoformat(),
        "date_range": f"{since_date} to {until_date}",
    }
