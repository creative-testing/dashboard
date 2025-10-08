"""
Router pour la gestion des comptes publicitaires et informations utilisateur
"""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import Dict, Any

from ..database import get_db
from ..dependencies.auth import get_current_tenant_id, get_current_user_id
from .. import models

router = APIRouter()


@router.get("/me")
async def get_me(
    current_tenant_id: UUID = Depends(get_current_tenant_id),
    current_user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Retourne les informations de l'utilisateur connecté

    🔒 Protected endpoint - requires valid JWT (header or cookie)

    Returns:
        {
            "tenant_id": "uuid",
            "user_id": "uuid",
            "email": "user@example.com",
            "name": "User Name"
        }
    """
    user = db.get(models.User, current_user_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "tenant_id": str(current_tenant_id),
        "user_id": str(current_user_id),
        "email": user.email,
        "name": user.name,
    }


@router.get("/")
async def list_accounts(
    current_tenant_id: UUID = Depends(get_current_tenant_id),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Liste tous les ad accounts du tenant actuel

    🔒 Protected endpoint - requires valid JWT
    🏢 Tenant-isolated - only returns accounts for authenticated tenant

    Returns:
        {
            "accounts": [...]
        }
    """
    accounts = db.execute(
        select(models.AdAccount).where(
            models.AdAccount.tenant_id == current_tenant_id
        )
    ).scalars().all()

    return {
        "accounts": [
            {
                "id": str(acc.id),
                "fb_account_id": acc.fb_account_id,
                "name": acc.name,
                "profile": acc.profile,
                "last_refresh_at": acc.last_refresh_at.isoformat() if acc.last_refresh_at else None,
            }
            for acc in accounts
        ]
    }


@router.post("/refresh/{account_id}")
async def refresh_account(
    account_id: str,
    current_tenant_id: UUID = Depends(get_current_tenant_id),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Déclenche un refresh des données pour un compte

    🔒 Protected endpoint - requires valid JWT
    🏢 Tenant-isolated - can only refresh accounts belonging to your tenant

    Flow:
    1. Vérifie ownership du compte (tenant isolation)
    2. Fetch ads + insights depuis Meta API via OAuth token
    3. Transform en format optimisé (meta_v1.json, agg_v1.json, summary_v1.json)
    4. Écrit dans storage
    5. Update last_refresh_at

    TODO:
    - Vérifier les quotas (subscription.quota_refresh_per_day)
    - Enqueue via Redis pour async (pour l'instant sync MVP)
    """
    from ..services.refresher import refresh_account_data, RefreshError

    try:
        result = await refresh_account_data(
            ad_account_id=account_id,
            tenant_id=current_tenant_id,
            db=db
        )
        return result

    except RefreshError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Refresh failed: {str(e)}"
        )
