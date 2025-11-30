"""
Router pour la gestion des comptes publicitaires et informations utilisateur
"""
from uuid import UUID
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import Dict, Any, Optional, List
import asyncio

from ..database import get_db, SessionLocal
from ..dependencies.auth import get_current_tenant_id, get_current_user_id
from .. import models
from ..models.refresh_job import RefreshJob, JobStatus
from ..services.refresher import sync_account_data, RefreshError
from ..config import settings
from ..utils.jwt import create_access_token

router = APIRouter()

# Parallélisation pour le refresh initial (nouveau venu)
PARALLEL_REFRESH_LIMIT = 5  # 5 comptes en parallèle max


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

        # 2. Exécuter la sync (30s-15min selon la taille du compte)
        await sync_account_data(
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


async def _run_parallel_refresh(
    accounts: List[models.AdAccount],
    tenant_id: UUID,
    semaphore_limit: int = PARALLEL_REFRESH_LIMIT
) -> Dict[str, Any]:
    """
    Exécute le refresh de plusieurs comptes EN PARALLÈLE avec sémaphore.

    Args:
        accounts: Liste des AdAccount à refresh
        tenant_id: UUID du tenant
        semaphore_limit: Nombre max de refreshs simultanés

    Returns:
        {"ok": int, "errors": int, "total_time_seconds": float}
    """
    import time

    semaphore = asyncio.Semaphore(semaphore_limit)
    results = {"ok": 0, "errors": 0}
    start_time = time.time()

    async def refresh_one(account: models.AdAccount):
        async with semaphore:
            db = SessionLocal()
            try:
                # Créer job
                job = RefreshJob(
                    tenant_id=tenant_id,
                    ad_account_id=account.id,
                    status=JobStatus.RUNNING,
                    started_at=_utcnow()
                )
                db.add(job)
                db.commit()
                db.refresh(job)

                # Sync
                await sync_account_data(
                    ad_account_id=account.fb_account_id,
                    tenant_id=tenant_id,
                    db=db
                )

                # Marquer OK
                job.status = JobStatus.OK
                job.finished_at = _utcnow()
                db.commit()
                results["ok"] += 1

            except Exception as e:
                # Marquer ERROR
                if job:
                    job.status = JobStatus.ERROR
                    job.error = str(e)[:500]
                    job.finished_at = _utcnow()
                    db.commit()
                results["errors"] += 1
            finally:
                db.close()

    # Lancer tous les refreshs en parallèle (limités par sémaphore)
    await asyncio.gather(*[refresh_one(acc) for acc in accounts])

    results["total_time_seconds"] = time.time() - start_time
    return results


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


@router.post("/refresh-tenant-accounts")
async def refresh_tenant_accounts(
    background_tasks: BackgroundTasks,
    current_tenant_id: UUID = Depends(get_current_tenant_id),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Déclenche le refresh de TOUS les ad accounts du tenant authentifié.

    🔒 Protected - requires valid JWT
    🏢 Tenant-isolated - only refreshes YOUR accounts
    ⚡ Async - returns immediately, jobs run in background

    Use case: Nouvel utilisateur qui vient de se connecter via OAuth
    et ne veut pas attendre le cron (2h max).

    Returns:
        {
            "status": "processing",
            "accounts_total": 60,
            "jobs_created": 60,
            "estimated_time_minutes": 15
        }
    """
    # 1. Récupérer tous les ad accounts du tenant
    accounts = db.execute(
        select(models.AdAccount).where(
            models.AdAccount.tenant_id == current_tenant_id
        )
    ).scalars().all()

    if not accounts:
        return {
            "status": "no_accounts",
            "accounts_total": 0,
            "jobs_created": 0,
            "estimated_time_minutes": 0
        }

    # 2. Créer un job pour chaque compte (même logique que le cron)
    jobs_created = []
    for account in accounts:
        # Check idempotence - skip if already running
        existing = db.execute(
            select(RefreshJob).where(
                RefreshJob.tenant_id == current_tenant_id,
                RefreshJob.ad_account_id == account.id,
                RefreshJob.status.in_([JobStatus.QUEUED, JobStatus.RUNNING])
            )
        ).scalar_one_or_none()

        if existing:
            jobs_created.append({
                "account_id": account.fb_account_id,
                "job_id": str(existing.id),
                "already_running": True
            })
            continue

        # Create new job
        job = RefreshJob(
            tenant_id=current_tenant_id,
            ad_account_id=account.id,
            status=JobStatus.QUEUED
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        # Launch in background
        background_tasks.add_task(
            _run_refresh_job,
            job.id,
            account.fb_account_id,
            current_tenant_id
        )
        jobs_created.append({
            "account_id": account.fb_account_id,
            "job_id": str(job.id),
            "already_running": False
        })

    # Estimation: ~15s par compte, minimum 15 minutes
    estimated_minutes = max(15, len(accounts) // 4)

    return {
        "status": "processing",
        "accounts_total": len(accounts),
        "jobs_created": len(jobs_created),
        "estimated_time_minutes": estimated_minutes,
        "jobs": jobs_created
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
    # Temporairement désactivé pour test en production
    # TODO: Ajouter ENABLE_TEST_ENDPOINTS env var ou retirer après test
    # if not settings.DEBUG:
    #     raise HTTPException(status_code=404, detail="Not found")

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

        # Lancer la sync de manière synchrone
        try:
            result = await sync_account_data(
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


@router.get("/dev/check-files/{fb_account_id}")
async def dev_check_files(fb_account_id: str) -> Dict[str, Any]:
    """
    🔍 DEBUG ONLY: Vérifie les fichiers générés pour un compte

    Retourne la liste des fichiers avec leur taille pour vérifier
    que le refresh a bien généré les données optimisées.

    Returns:
        {
            "account_id": "act_XXX",
            "tenant_id": "uuid",
            "files": [
                {"name": "meta_v1.json", "size_bytes": 12345},
                ...
            ]
        }
    """
    from ..services import storage

    db = SessionLocal()
    try:
        # Trouver le compte
        ad_account = db.execute(
            select(models.AdAccount).where(
                models.AdAccount.fb_account_id == fb_account_id
            )
        ).scalar_one_or_none()

        if not ad_account:
            raise HTTPException(
                status_code=404,
                detail=f"Ad account {fb_account_id} not found"
            )

        tenant_id = ad_account.tenant_id
        base_path = f"tenants/{tenant_id}/accounts/{fb_account_id}/data/optimized"

        # Liste des fichiers à vérifier
        expected_files = ["meta_v1.json", "agg_v1.json", "summary_v1.json", "manifest.json"]
        files_info = []

        for filename in expected_files:
            storage_key = f"{base_path}/{filename}"
            try:
                content = storage.get_object(storage_key)
                files_info.append({
                    "name": filename,
                    "size_bytes": len(content),
                    "exists": True
                })
            except storage.StorageError:
                files_info.append({
                    "name": filename,
                    "size_bytes": 0,
                    "exists": False
                })

        return {
            "account_id": fb_account_id,
            "tenant_id": str(tenant_id),
            "base_path": base_path,
            "files": files_info
        }

    finally:
        db.close()


@router.get("/dev/generate-jwt/{fb_account_id}")
async def dev_generate_jwt(fb_account_id: str) -> Dict[str, Any]:
    """
    🔑 DEBUG ONLY: Génère un JWT pour accéder au dashboard d'un compte

    Génère un JWT d'authentification backend pour le tenant qui possède
    ce compte. Le JWT permet au dashboard de télécharger les fichiers JSON.

    Returns:
        {
            "success": true,
            "jwt_token": "eyJ...",
            "tenant_id": "uuid",
            "account_id": "act_XXX",
            "dashboard_url": "https://...?account_id=act_XXX&token=eyJ...",
            "expires_in_seconds": 604800  # 7 days
        }
    """
    db = SessionLocal()
    try:
        # 1. Trouver le compte
        ad_account = db.execute(
            select(models.AdAccount).where(
                models.AdAccount.fb_account_id == fb_account_id
            )
        ).scalar_one_or_none()

        if not ad_account:
            raise HTTPException(
                status_code=404,
                detail=f"Ad account {fb_account_id} not found"
            )

        tenant_id = ad_account.tenant_id

        # 2. Trouver un user de ce tenant (pour le JWT)
        user = db.execute(
            select(models.User).where(
                models.User.tenant_id == tenant_id
            )
        ).first()

        if not user:
            raise HTTPException(
                status_code=500,
                detail=f"No user found for tenant {tenant_id}"
            )

        user = user[0]  # unpack from tuple

        # 3. Générer le JWT
        jwt_token = create_access_token(
            user_id=user.id,
            tenant_id=tenant_id
        )

        # 4. Construire l'URL du dashboard (direct vers index-saas.html)
        # Note: index-saas.html est le vrai dashboard, oauth-callback.html est juste un intermédiaire OAuth
        from urllib.parse import urlencode

        dashboard_params = {
            "account_id": fb_account_id,
            "account": ad_account.name,
            "token": jwt_token,
            "tenant_id": str(tenant_id),
            "locked": "1"  # Verrouiller le sélecteur de compte
        }

        # Pointer vers index-saas.html directement (pas oauth-callback.html qui est pour OAuth callback)
        base_url = settings.DASHBOARD_URL.replace("oauth-callback.html", "index-saas.html")
        dashboard_url = f"{base_url}?{urlencode(dashboard_params)}"

        return {
            "success": True,
            "jwt_token": jwt_token,
            "tenant_id": str(tenant_id),
            "account_id": fb_account_id,
            "account_name": ad_account.name,
            "dashboard_url": dashboard_url,
            "expires_in_seconds": 7 * 24 * 60 * 60  # 7 jours
        }

    finally:
        db.close()


@router.get("/dev/count-meta-accounts")
async def count_meta_accounts(tenant_id: str = "c0c595ab-3903-4256-b8d7-cb9709ac9206") -> Dict[str, Any]:
    """
    🧪 DEBUG: Compare nombre de comptes Meta API vs DB

    Vérifie si le fix de pagination a fonctionné sans toucher aux données.
    Idéal pour valider avant de re-sync.

    Args:
        tenant_id: Tenant UUID (défaut = production)

    Returns:
        {
            "meta_api_count": 70,
            "database_count": 25,
            "missing_count": 45,
            "fix_needed": true/false
        }
    """
    from uuid import UUID
    from cryptography.fernet import Fernet
    from ..services.meta_client import meta_client

    db = SessionLocal()
    fernet = Fernet(settings.TOKEN_ENCRYPTION_KEY.encode())

    try:
        # Get tenant + token
        tenant = db.execute(
            select(models.Tenant).where(models.Tenant.id == UUID(tenant_id))
        ).scalar_one_or_none()

        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")

        token_row = db.execute(
            select(models.OAuthToken).where(models.OAuthToken.tenant_id == UUID(tenant_id))
        ).scalar_one_or_none()

        if not token_row:
            raise HTTPException(status_code=404, detail="No OAuth token")

        # Decrypt token
        access_token = fernet.decrypt(token_row.access_token).decode()

        # Call Meta API avec fix de pagination
        accounts_from_api = await meta_client.get_ad_accounts(access_token)

        # Count in DB
        accounts_in_db = db.execute(
            select(models.AdAccount).where(models.AdAccount.tenant_id == UUID(tenant_id))
        ).scalars().all()

        missing_count = len(accounts_from_api) - len(accounts_in_db)

        return {
            "success": True,
            "tenant_id": tenant_id,
            "tenant_name": tenant.name,
            "meta_api_count": len(accounts_from_api),
            "database_count": len(accounts_in_db),
            "missing_count": missing_count,
            "fix_needed": missing_count > 0,
            "sample_from_api": [f"{a['name']} ({a['id']})" for a in accounts_from_api[:5]],
            "sample_from_db": [f"{a.name} ({a.fb_account_id})" for a in accounts_in_db[:5]]
        }

    finally:
        db.close()


@router.post("/dev/seed-production")
async def seed_production_tenant() -> Dict[str, Any]:
    """
    🌱 Seed tenant de production pour Ads Alchimie

    Crée automatiquement:
    - Tenant "Ads Alchimie" (meta_user_id = "production")
    - User "Production User"
    - OAuth token de production (depuis .env)
    - TOUS les ad accounts accessibles via le token (60+)
    - Subscription FREE

    Idempotent: peut être appelé plusieurs fois sans erreur

    Returns:
        {
            "success": true,
            "tenant_id": "uuid",
            "accounts_added": 64,
            "accounts": ["act_XXX", ...]
        }
    """
    from cryptography.fernet import Fernet
    from sqlalchemy.dialects.postgresql import insert
    from sqlalchemy import func
    import httpx

    # Temporairement désactivé pour test en production
    # if not settings.DEBUG:
    #     raise HTTPException(status_code=404, detail="Not found")

    # Lire token de production depuis .env
    production_token = settings.FACEBOOK_ACCESS_TOKEN
    if not production_token:
        raise HTTPException(status_code=500, detail="FACEBOOK_ACCESS_TOKEN not configured in .env")

    db = SessionLocal()
    fernet = Fernet(settings.TOKEN_ENCRYPTION_KEY.encode())

    try:
        # 1. Créer/update tenant "Ads Alchimie"
        stmt = insert(models.Tenant).values(
            meta_user_id="production",
            name="Ads Alchimie (Production)",
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["meta_user_id"],
            set_={"name": stmt.excluded.name, "updated_at": func.now()},
        )
        db.execute(stmt)
        db.flush()

        tenant = db.execute(
            select(models.Tenant).where(models.Tenant.meta_user_id == "production")
        ).scalar_one()

        # 2. Créer/update user
        stmt = insert(models.User).values(
            tenant_id=tenant.id,
            meta_user_id="production_user",
            email="production@ads-alchimie.com",
            name="Ads Alchimie Team",
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["tenant_id", "meta_user_id"],
            set_={
                "email": stmt.excluded.email,
                "name": stmt.excluded.name,
                "updated_at": func.now(),
            },
        )
        db.execute(stmt)
        db.flush()

        user = db.execute(
            select(models.User).where(
                models.User.tenant_id == tenant.id,
                models.User.meta_user_id == "production_user"
            )
        ).scalar_one()

        # 3. Stocker OAuth token (chiffré)
        token_encrypted = fernet.encrypt(production_token.encode()).decode()
        expires_at = datetime.now(timezone.utc) + timedelta(days=60)

        stmt = insert(models.OAuthToken).values(
            tenant_id=tenant.id,
            user_id=user.id,
            provider="meta",
            fb_user_id="production_user",
            access_token=token_encrypted.encode(),
            expires_at=expires_at,
            scopes=["ads_read", "email", "public_profile"],
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["user_id", "provider"],
            set_={
                "access_token": stmt.excluded.access_token,
                "expires_at": stmt.excluded.expires_at,
            },
        )
        db.execute(stmt)

        # 4. Fetch TOUS les ad accounts via Meta API (utilise meta_client centralisé)
        from ..services.meta_client import meta_client

        all_accounts = await meta_client.get_ad_accounts(
            access_token=production_token,
            fields="id,name,account_status"
        )

        # 5. Insérer ad accounts dans la DB
        accounts_added = []
        for account in all_accounts:
            fb_account_id = account["id"]
            account_name = account.get("name", "Unknown")

            stmt = insert(models.AdAccount).values(
                tenant_id=tenant.id,
                fb_account_id=fb_account_id,
                name=account_name,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["tenant_id", "fb_account_id"],
                set_={"name": stmt.excluded.name},
            )
            db.execute(stmt)
            accounts_added.append(fb_account_id)

        # 6. Créer subscription FREE si n'existe pas
        existing_subscription = db.execute(
            select(models.Subscription).where(models.Subscription.tenant_id == tenant.id)
        ).scalar_one_or_none()

        if not existing_subscription:
            subscription = models.Subscription(
                tenant_id=tenant.id,
                plan="free",
                status="active",
                quota_accounts=100,  # Production: 100 comptes max
                quota_refresh_per_day=24,  # 1 refresh/heure
            )
            db.add(subscription)

        db.commit()

        return {
            "success": True,
            "tenant_id": str(tenant.id),
            "tenant_name": tenant.name,
            "accounts_added": len(accounts_added),
            "accounts": accounts_added,
        }

    except httpx.HTTPError as e:
        db.rollback()
        raise HTTPException(status_code=502, detail=f"Meta API error: {str(e)}")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Seed error: {str(e)}")
    finally:
        db.close()


@router.post("/dev/generate-dashboard-link")
async def generate_dashboard_link(tenant_id: str) -> Dict[str, Any]:
    """
    Génère une URL dashboard permanente (JWT 7 jours) pour un tenant

    Args:
        tenant_id: UUID du tenant

    Returns:
        {
            "dashboard_url": "https://creative-testing.github.io/dashboard/index-saas.html?token=XXX",
            "tenant_id": "uuid",
            "tenant_name": "Ads Alchimie (Production)",
            "expires_in_days": 7
        }
    """
    from uuid import UUID

    db = SessionLocal()

    try:
        # Get tenant
        tenant = db.execute(
            select(models.Tenant).where(models.Tenant.id == UUID(tenant_id))
        ).scalar_one_or_none()

        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")

        # Get user
        user = db.execute(
            select(models.User).where(models.User.tenant_id == UUID(tenant_id))
        ).first()

        if not user:
            raise HTTPException(status_code=404, detail="User not found for tenant")

        user = user[0]

        # Generate JWT (7 days)
        token = create_access_token(user.id, tenant.id, expires_delta=timedelta(days=7))

        # Build dashboard URL
        dashboard_url = f"https://creative-testing.github.io/dashboard/index-saas.html?token={token}&tenant_id={tenant.id}"

        return {
            "dashboard_url": dashboard_url,
            "tenant_id": str(tenant.id),
            "tenant_name": tenant.name,
            "expires_in_days": 7
        }

    finally:
        db.close()


@router.post("/dev/inject-production-token")
def inject_production_token(
    access_token: str,
    tenant_id: str = "c0c595ab-3903-4256-b8d7-cb9709ac9206",
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    🔧 BOOTSTRAP: Injecte un token Meta dans le tenant de production

    Permet de migrer le token existant (GitHub Secrets) dans la DB
    pour que le refresh fonctionne sans que les patrons fassent OAuth

    Args:
        access_token: Token Meta long-lived (celui de GitHub Secrets)
        tenant_id: Tenant UUID (défaut = production)

    Returns:
        {"success": true, "tenant_id": "...", "message": "..."}
    """
    from uuid import UUID
    from datetime import datetime, timedelta
    from sqlalchemy.dialects.postgresql import insert
    from cryptography.fernet import Fernet

    # Fernet pour chiffrer le token
    fernet = Fernet(settings.TOKEN_ENCRYPTION_KEY.encode())

    try:
        # 1. Vérifier tenant existe
        tenant = db.execute(
            select(models.Tenant).where(models.Tenant.id == UUID(tenant_id))
        ).scalar_one_or_none()

        if not tenant:
            raise HTTPException(status_code=404, detail=f"Tenant {tenant_id} not found")

        # 2. Créer user fictif si n'existe pas (pour structure DB complète)
        user = db.execute(
            select(models.User).where(models.User.tenant_id == UUID(tenant_id))
        ).first()

        if not user:
            user = models.User(
                tenant_id=UUID(tenant_id),
                meta_user_id="production_legacy",
                email="production@adsalchemy.com",
                name="Production (Legacy)"
            )
            db.add(user)
            db.flush()
        else:
            user = user[0]

        # 3. Chiffrer le token
        token_encrypted = fernet.encrypt(access_token.encode()).decode()

        # 4. Insérer/Update token OAuth
        expires_at = datetime.utcnow() + timedelta(days=60)  # Long-lived token

        stmt = insert(models.OAuthToken).values(
            tenant_id=UUID(tenant_id),
            user_id=user.id,
            provider="meta",
            fb_user_id="production_legacy",
            access_token=token_encrypted.encode(),
            expires_at=expires_at,
            scopes=["ads_read", "public_profile"]
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["user_id", "provider"],
            set_={
                "access_token": stmt.excluded.access_token,
                "expires_at": stmt.excluded.expires_at,
                "scopes": stmt.excluded.scopes
            }
        )
        db.execute(stmt)
        db.commit()

        return {
            "success": True,
            "tenant_id": tenant_id,
            "tenant_name": tenant.name,
            "user_id": str(user.id),
            "message": "✅ Token de Meta insertado con éxito. El refresh ya puede ejecutarse."
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/dev/refresh-all-production")
async def refresh_all_production_accounts(
    background_tasks: BackgroundTasks,
    tenant_id: str = "c0c595ab-3903-4256-b8d7-cb9709ac9206",
    limit: Optional[int] = None
) -> Dict[str, Any]:
    """
    🔄 Refresh TOUS les ad accounts d'un tenant (par défaut: Ads Alchimie Production)

    Args:
        tenant_id: Tenant UUID (défaut = production tenant)
        limit: Limite le nombre de comptes à refresh (pour tests rapides)

    Returns:
        {
            "tenant_id": "uuid",
            "tenant_name": "Ads Alchimie (Production)",
            "accounts_total": 70,
            "accounts_refreshing": 70,
            "jobs": [{"account_id": "act_XXX", "account_name": "...", "job_id": "uuid"}]
        }
    """
    from uuid import UUID
    from cryptography.fernet import Fernet

    db = SessionLocal()

    try:
        tenant = db.execute(
            select(models.Tenant).where(models.Tenant.id == UUID(tenant_id))
        ).scalar_one_or_none()

        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")

        # Get all ad accounts for this tenant
        accounts = db.execute(
            select(models.AdAccount).where(models.AdAccount.tenant_id == UUID(tenant_id))
        ).scalars().all()

        # Apply limit if specified (for testing)
        if limit:
            accounts = accounts[:limit]

        # Launch refresh jobs using same mechanism as /refresh/{fb_account_id}
        jobs_launched = []

        for account in accounts:
            # Check for existing running job (idempotence)
            existing_job = db.execute(
                select(RefreshJob).where(
                    RefreshJob.tenant_id == UUID(tenant_id),
                    RefreshJob.ad_account_id == account.id,
                    RefreshJob.status.in_([JobStatus.QUEUED, JobStatus.RUNNING])
                )
            ).scalar_one_or_none()

            if existing_job:
                # Skip if already running
                jobs_launched.append({
                    "account_id": account.fb_account_id,
                    "account_name": account.name,
                    "job_id": str(existing_job.id),
                    "already_running": True
                })
                continue

            # Create new job
            job = RefreshJob(
                tenant_id=UUID(tenant_id),
                ad_account_id=account.id,
                status=JobStatus.QUEUED
            )
            db.add(job)
            db.commit()
            db.refresh(job)

            # Launch in background using BackgroundTasks
            background_tasks.add_task(
                _run_refresh_job,
                job.id,
                account.fb_account_id,
                UUID(tenant_id)
            )

            jobs_launched.append({
                "account_id": account.fb_account_id,
                "account_name": account.name,
                "job_id": str(job.id),
                "already_running": False
            })

        return {
            "success": True,
            "tenant_id": str(tenant.id),
            "tenant_name": tenant.name,
            "accounts_total": len(accounts),
            "accounts_refreshing": len(jobs_launched),
            "jobs": jobs_launched,
            "message": f"🔄 Refresh lanzado para {len(jobs_launched)} cuentas. Duración estimada: ~{len(jobs_launched) * 0.5:.0f} minutos"
        }

    finally:
        db.close()
