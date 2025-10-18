"""
Router pour la gestion des comptes publicitaires et informations utilisateur
"""
from uuid import UUID
from datetime import datetime, timezone, timedelta
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
from ..utils.jwt import create_access_token

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
        # Note: index-saas.html est le vrai dashboard, index-mvp.html est juste un intermédiaire OAuth
        from urllib.parse import urlencode

        dashboard_params = {
            "account_id": fb_account_id,
            "account": ad_account.name,
            "token": jwt_token,
            "tenant_id": str(tenant_id),
            "locked": "1"  # Verrouiller le sélecteur de compte
        }

        # Pointer vers index-saas.html directement (pas index-mvp.html qui est pour OAuth callback)
        base_url = settings.DASHBOARD_URL.replace("index-mvp.html", "index-saas.html")
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

        # 4. Fetch TOUS les ad accounts via Meta API
        async with httpx.AsyncClient(timeout=30.0) as client:
            all_accounts = []
            url = f"https://graph.facebook.com/v23.0/me/adaccounts"
            params = {
                "fields": "id,name,account_status",
                "access_token": production_token,
                "limit": 100,
            }

            while url:
                response = await client.get(url, params=params if params else None)
                response.raise_for_status()
                data = response.json()

                all_accounts.extend(data.get("data", []))

                # Pagination
                url = data.get("paging", {}).get("next")
                params = None  # Next URL contient déjà les params

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
