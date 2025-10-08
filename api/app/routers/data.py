"""
Router pour servir les données optimisées (proxy vers R2/S3)
"""
from typing import Dict, Any
from uuid import UUID
from hashlib import md5
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import select
from cryptography.fernet import Fernet

from ..database import get_db
from ..config import settings
from ..services.meta_client import meta_client, MetaAPIError
from ..services import storage
from ..dependencies.auth import get_current_tenant_id
from .. import models

router = APIRouter()

# Fernet pour déchiffrer les tokens
fernet = Fernet(settings.TOKEN_ENCRYPTION_KEY.encode())


async def get_current_tenant(db: Session = Depends(get_db)) -> models.Tenant:
    """Mock - TODO: implémenter avec JWT"""
    raise HTTPException(status_code=401, detail="Not authenticated")


@router.get("/files/{act_id}/{filename}")
async def get_file(
    act_id: str,
    filename: str,
    current_tenant_id: UUID = Depends(get_current_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Proxy sécurisé pour servir les fichiers de données optimisées

    🔒 Protected endpoint - requires valid JWT
    🏢 Tenant-isolated - only serves files for authenticated tenant's accounts
    📦 Serves: meta_v1.json, agg_v1.json, summary_v1.json

    Args:
        act_id: Ad account ID (e.g., "act_123456")
        filename: File to serve (meta_v1.json | agg_v1.json | summary_v1.json)

    Returns:
        JSON file contents with cache headers
    """
    # 1. Vérifier que le nom de fichier est valide (whitelist)
    allowed_files = {"meta_v1.json", "agg_v1.json", "summary_v1.json"}
    if filename not in allowed_files:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid filename. Allowed: {', '.join(allowed_files)}"
        )

    # 2. Vérifier que l'ad account appartient au tenant (tenant isolation)
    ad_account = db.execute(
        select(models.AdAccount).where(
            models.AdAccount.fb_account_id == act_id,
            models.AdAccount.tenant_id == current_tenant_id
        )
    ).scalar_one_or_none()

    if not ad_account:
        raise HTTPException(
            status_code=404,
            detail=f"Ad account {act_id} not found for your workspace"
        )

    # 3. Construire la clé de stockage
    storage_key = f"tenants/{current_tenant_id}/accounts/{act_id}/{filename}"

    # 4. Lire le fichier depuis le storage
    try:
        file_data = storage.get_object(storage_key)
    except storage.StorageError as e:
        raise HTTPException(
            status_code=404,
            detail=f"File not found: {filename} ({str(e)})"
        )

    # 5. Générer ETag pour validation de cache
    etag = md5(file_data).hexdigest()

    # 6. Retourner avec headers de cache sécurisés
    return Response(
        content=file_data,
        media_type="application/json",
        headers={
            "Cache-Control": "private, max-age=300",  # 5 min, private to prevent CDN sharing
            "ETag": f'"{etag}"',  # For cache validation
            "Vary": "Authorization, Cookie",  # Cache varies by auth method
            "X-Tenant-Id": str(current_tenant_id),
            "X-Account-Id": act_id,
        }
    )


@router.get("/campaigns")
async def get_campaigns(
    ad_account_id: str = Query(..., description="Ad account ID (ex: act_123456)"),
    fields: str = Query("id,name,status", description="Comma-separated fields to retrieve"),
    limit: int = Query(25, le=100, description="Number of campaigns to retrieve"),
    current_tenant_id: UUID = Depends(get_current_tenant_id),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Récupère les campaigns d'un ad account via le token OAuth stocké.

    🔒 Protected endpoint - requires valid JWT token
    🏢 Tenant-isolated - only returns data for authenticated tenant

    Returns:
        {
            "ad_account_id": "act_123456",
            "tenant_id": "uuid",
            "campaigns": [...],
            "count": 10
        }
    """
    # 1. Trouver l'ad account dans la DB (filtré par tenant pour isolation)
    ad_account = db.execute(
        select(models.AdAccount).where(
            models.AdAccount.fb_account_id == ad_account_id,
            models.AdAccount.tenant_id == current_tenant_id  # 🔒 CRITICAL: tenant isolation
        )
    ).scalar_one_or_none()

    if not ad_account:
        raise HTTPException(
            status_code=404,
            detail=f"Ad account {ad_account_id} not found for your workspace. Please connect it via OAuth first."
        )

    # 2. Récupérer le token OAuth associé au tenant
    oauth_token = db.execute(
        select(models.OAuthToken).where(
            models.OAuthToken.tenant_id == ad_account.tenant_id,
            models.OAuthToken.provider == "meta"
        )
    ).scalar_one_or_none()

    if not oauth_token:
        raise HTTPException(
            status_code=404,
            detail=f"No OAuth token found for tenant {ad_account.tenant_id}. Please re-authenticate."
        )

    # 3. Déchiffrer le token
    try:
        access_token = fernet.decrypt(oauth_token.access_token).decode()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to decrypt access token: {str(e)}"
        )

    # 4. Appeler l'API Meta pour récupérer les campaigns
    try:
        campaigns = await meta_client.get_campaigns(
            ad_account_id=ad_account_id,
            access_token=access_token,
            fields=fields,
            limit=limit
        )
    except MetaAPIError as e:
        # Si token expiré ou invalide, renvoyer 401
        if "expired" in str(e).lower() or "invalid" in str(e).lower():
            raise HTTPException(
                status_code=401,
                detail=f"OAuth token expired or invalid. Please re-authenticate. Error: {str(e)}"
            )
        # Autres erreurs Meta API
        raise HTTPException(
            status_code=502,
            detail=f"Meta API error: {str(e)}"
        )

    # 5. Retourner les données
    return {
        "ad_account_id": ad_account_id,
        "tenant_id": str(ad_account.tenant_id),
        "campaigns": campaigns,
        "count": len(campaigns),
    }
