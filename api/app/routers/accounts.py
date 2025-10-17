"""
Router pour la gestion des comptes publicitaires et informations utilisateur
"""
from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import Dict, Any

from ..database import get_db, SessionLocal
from ..dependencies.auth import get_current_tenant_id, get_current_user_id
from .. import models
from ..models.refresh_job import RefreshJob, JobStatus
from ..services.refresher import refresh_account_data, RefreshError
from ..config import settings

router = APIRouter()


def _utcnow():
    """Helper pour datetime UTC"""
    return datetime.now(timezone.utc)


async def _run_refresh_job(job_id: UUID, fb_account_id: str, tenant_id: UUID):
    """
    Exécute le refresh en background et met à jour le statut du job.

    Cette fonction tourne en background via FastAPI BackgroundTasks.
    Elle crée sa propre session DB pour éviter les conflits.
    """
    db = SessionLocal()
    try:
        # 1. Marquer le job comme RUNNING
        job = db.get(RefreshJob, job_id)
        if not job:
            return
        job.status = JobStatus.RUNNING
        job.started_at = _utcnow()
        db.commit()

        # 2. Exécuter le refresh (30s-15min selon la taille du compte)
        await refresh_account_data(
            ad_account_id=fb_account_id,
            tenant_id=tenant_id,
            db=db
        )

        # 3. Marquer comme OK
        job = db.get(RefreshJob, job_id)
        if job:
            job.status = JobStatus.OK
            job.finished_at = _utcnow()
            db.commit()

    except Exception as e:
        # 4. En cas d'erreur, marquer comme ERROR
        job = db.get(RefreshJob, job_id)
        if job:
            job.status = JobStatus.ERROR
            job.error = str(e)[:1000]  # Limiter à 1000 chars
            job.finished_at = _utcnow()
            db.commit()
    finally:
        db.close()


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


@router.post("/refresh/{fb_account_id}")
async def trigger_refresh(
    fb_account_id: str,
    background_tasks: BackgroundTasks,
    current_tenant_id: UUID = Depends(get_current_tenant_id),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Déclenche un refresh asynchrone des données pour un compte

    🔒 Protected endpoint - requires valid JWT
    🏢 Tenant-isolated - can only refresh accounts belonging to your tenant
    ⚡ Asynchronous - returns immediately with job_id, polling required

    Flow:
    1. Vérifie ownership du compte (tenant isolation)
    2. Crée un RefreshJob (status=QUEUED)
    3. Lance le refresh en background
    4. Retourne immédiatement avec job_id

    Returns:
        {
            "status": "processing",
            "job_id": "uuid",
            "already_processing": bool
        }
    """
    # 1. Vérifier que l'ad account appartient au tenant
    ad_account = db.execute(
        select(models.AdAccount).where(
            models.AdAccount.fb_account_id == fb_account_id,
            models.AdAccount.tenant_id == current_tenant_id
        )
    ).scalar_one_or_none()

    if not ad_account:
        raise HTTPException(
            status_code=404,
            detail=f"Ad account {fb_account_id} not found for your workspace"
        )

    # 2. Vérifier si un job est déjà en cours (idempotence)
    existing_job = db.execute(
        select(RefreshJob).where(
            RefreshJob.tenant_id == current_tenant_id,
            RefreshJob.ad_account_id == ad_account.id,
            RefreshJob.status.in_([JobStatus.QUEUED, JobStatus.RUNNING])
        )
    ).scalar_one_or_none()

    if existing_job:
        return {
            "status": "processing",
            "job_id": str(existing_job.id),
            "already_processing": True
        }

    # 3. Créer un nouveau job
    job = RefreshJob(
        tenant_id=current_tenant_id,
        ad_account_id=ad_account.id,
        status=JobStatus.QUEUED
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # 4. Lancer le refresh en background
    background_tasks.add_task(
        _run_refresh_job,
        job.id,
        fb_account_id,
        current_tenant_id
    )

    return {
        "status": "processing",
        "job_id": str(job.id),
        "already_processing": False
    }


@router.get("/refresh/status/{job_id}")
async def get_refresh_status(
    job_id: UUID,
    current_tenant_id: UUID = Depends(get_current_tenant_id),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Récupère le statut d'un job de refresh

    🔒 Protected endpoint - requires valid JWT
    🏢 Tenant-isolated - can only check jobs belonging to your tenant

    Returns:
        {
            "status": "queued" | "running" | "ok" | "error",
            "started_at": "ISO datetime" | null,
            "finished_at": "ISO datetime" | null,
            "error": "error message" | null
        }
    """
    job = db.get(RefreshJob, job_id)

    if not job or job.tenant_id != current_tenant_id:
        raise HTTPException(
            status_code=404,
            detail="Job not found"
        )

    return {
        "status": job.status.value,  # Convertir enum en string
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "error": job.error
    }


@router.post("/dev/test-refresh/{fb_account_id}")
async def dev_test_refresh(fb_account_id: str) -> Dict[str, Any]:
    """
    🚧 DEBUG ONLY: Test refresh avec vraies données (synchrone)

    Endpoint de test pour vérifier le refresh avec compte réel.
    Lance le refresh de manière synchrone et retourne immédiatement les stats.

    Utilise le token OAuth existant en DB (doit être valide).

    ⚠️ NO AUTH REQUIRED - endpoint protégé par DEBUG mode uniquement

    Returns:
        {
            "success": true,
            "ad_account_id": "act_XXX",
            "tenant_id": "uuid",
            "daily_rows_fetched": 150,
            "unique_ads": 50,
            "files_written": ["meta_v1.json", "agg_v1.json", "summary_v1.json", "manifest.json"],
            "date_range": "2025-01-01 to 2025-01-30"
        }
    """
    # Vérifier DEBUG mode
    if not settings.DEBUG:
        raise HTTPException(status_code=404, detail="Not found")

    # Créer session DB manuellement (évite chaîne de dépendances auth)
    db = SessionLocal()
    try:
        # Trouver le tenant associé à ce compte
        ad_account = db.execute(
            select(models.AdAccount).where(
                models.AdAccount.fb_account_id == fb_account_id
            )
        ).scalar_one_or_none()

        if not ad_account:
            raise HTTPException(
                status_code=404,
                detail=f"Ad account {fb_account_id} not found in database"
            )

        tenant_id = ad_account.tenant_id

        # Lancer le refresh de manière synchrone
        try:
            result = await refresh_account_data(
                ad_account_id=fb_account_id,
                tenant_id=tenant_id,
                db=db
            )

            return {
                "success": True,
                **result
            }

        except RefreshError as e:
            return {
                "success": False,
                "error": str(e),
                "ad_account_id": fb_account_id,
                "tenant_id": str(tenant_id)
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}",
                "ad_account_id": fb_account_id,
                "tenant_id": str(tenant_id)
            }
    finally:
        db.close()
