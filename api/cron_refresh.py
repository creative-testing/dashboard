#!/usr/bin/env python3
"""
🕐 Cron script pour refresh automatique de tous les tenants

Appelé toutes les 2h par le cron Docker sur VPS Vultr
Refresh les données Meta Ads de tous les tenants actifs

⚡ PARALLÉLISÉ: Utilise asyncio.Semaphore pour traiter 5 comptes simultanément
   Temps estimé: 20 min séquentiel → 3-4 min parallèle
"""
import asyncio
import gc
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Tuple

# Ajouter le répertoire parent au PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import select
from app.database import SessionLocal
from app import models
from app.models import JobStatus, RefreshJob
from app.services.refresher import sync_account_data, RefreshError
from app.services.demographics_fetcher import refresh_demographics_for_account, DemographicsError
from app.services.meta_client import meta_client
from cryptography.fernet import Fernet
from app.config import settings

# Configuration parallélisation
MAX_CONCURRENT_ACCOUNTS = 6  # Augmenté: VPS upgradé 4GB→8GB RAM (Nov 2024)
DELAY_BETWEEN_ACCOUNTS_MS = 200  # Petit délai pour éviter les burst de rate limit
MAX_CONSECUTIVE_ERRORS = 3  # Auto-disable après X erreurs 403 consécutives


async def refresh_single_account(
    account_id: int,
    account_fb_id: str,
    account_name: str,
    tenant_id: str,
    semaphore: asyncio.Semaphore
) -> Tuple[bool, str]:
    """
    Refresh un seul ad account (appelé en parallèle)

    ⚠️ IMPORTANT: Chaque tâche crée sa propre session DB pour éviter
    les race conditions avec asyncio.gather()

    Returns:
        (success: bool, message: str)
    """
    from uuid import UUID

    async with semaphore:
        # Petit délai pour éviter burst (stagger les requêtes)
        await asyncio.sleep(DELAY_BETWEEN_ACCOUNTS_MS / 1000)

        # ⚡ Créer une session DB dédiée pour cette tâche
        db = SessionLocal()

        try:
            # Check for existing running job (idempotence)
            existing_job = db.execute(
                select(RefreshJob).where(
                    RefreshJob.tenant_id == UUID(tenant_id),
                    RefreshJob.ad_account_id == account_id,
                    RefreshJob.status.in_([JobStatus.QUEUED, JobStatus.RUNNING])
                )
            ).scalar_one_or_none()

            if existing_job:
                return (True, f"⏭️ Skipped {account_fb_id} - already running")

            # Create job
            job = RefreshJob(
                tenant_id=UUID(tenant_id),
                ad_account_id=account_id,
                status=JobStatus.QUEUED
            )
            db.add(job)
            db.commit()
            db.refresh(job)

            try:
                # Update job status
                job.status = JobStatus.RUNNING
                job.started_at = datetime.now(timezone.utc)
                db.commit()

                # Run sync (insights data)
                result = await sync_account_data(
                    ad_account_id=account_fb_id,
                    tenant_id=UUID(tenant_id),
                    db=db
                )

                # 📊 Run demographics refresh (age/gender breakdowns)
                try:
                    demo_result = await refresh_demographics_for_account(
                        ad_account_id=account_fb_id,
                        tenant_id=UUID(tenant_id),
                        db=db
                    )
                    demo_periods = len(demo_result.get('periods_fetched', []))
                except DemographicsError as e:
                    # Demographics failure is non-fatal, log and continue
                    print(f"    ⚠️ Demographics failed for {account_fb_id}: {str(e)[:50]}")
                    demo_periods = 0
                except Exception as e:
                    print(f"    ⚠️ Demographics error for {account_fb_id}: {str(e)[:50]}")
                    demo_periods = 0

                # Mark job as completed
                job.status = JobStatus.OK
                job.finished_at = datetime.now(timezone.utc)

                # ✅ Reset consecutive errors on success
                account = db.execute(
                    select(models.AdAccount).where(models.AdAccount.id == account_id)
                ).scalar_one_or_none()
                if account and account.consecutive_errors > 0:
                    account.consecutive_errors = 0

                db.commit()

                demo_info = f" +{demo_periods}d" if demo_periods > 0 else ""
                return (True, f"✅ {account_fb_id} ({account_name}){demo_info}")

            except Exception as e:
                error_msg = str(e)[:500]
                job.status = JobStatus.ERROR
                job.error = error_msg
                job.finished_at = datetime.now(timezone.utc)

                # 🔴 Handle 403 errors: increment counter, auto-disable after MAX_CONSECUTIVE_ERRORS
                account = db.execute(
                    select(models.AdAccount).where(models.AdAccount.id == account_id)
                ).scalar_one_or_none()

                if account and "403" in error_msg:
                    account.consecutive_errors += 1
                    if account.consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                        account.is_disabled = True
                        account.disabled_reason = f"Auto-disabled: {MAX_CONSECUTIVE_ERRORS}+ consecutive 403 errors"
                        db.commit()
                        return (False, f"🚫 {account_fb_id}: DISABLED (403 x{account.consecutive_errors})")

                db.commit()
                return (False, f"❌ {account_fb_id}: {str(e)[:80]}")

        finally:
            # ⚡ Toujours fermer la session
            db.close()
            # 🧹 Force garbage collection pour libérer RAM entre chaque compte
            gc.collect()


async def refresh_tenant(tenant_id: str, tenant_name: str, db: SessionLocal):
    """
    Refresh tous les ad accounts d'un tenant EN PARALLÈLE

    ⚡ OPTIMISÉ: Utilise asyncio.Semaphore pour limiter la concurrence
    et éviter de dépasser les rate limits Meta API.

    Args:
        tenant_id: UUID du tenant
        tenant_name: Nom du tenant (pour logs)
        db: Session DB
    """
    from uuid import UUID

    print(f"\n🔄 Refreshing tenant: {tenant_name} ({tenant_id})")
    start_time = datetime.now(timezone.utc)

    try:
        # Get all ACTIVE ad accounts for this tenant (skip disabled)
        accounts = db.execute(
            select(models.AdAccount).where(
                models.AdAccount.tenant_id == UUID(tenant_id),
                models.AdAccount.is_disabled == False
            )
        ).scalars().all()

        # Count disabled for logging
        disabled_count = db.execute(
            select(models.AdAccount).where(
                models.AdAccount.tenant_id == UUID(tenant_id),
                models.AdAccount.is_disabled == True
            )
        ).scalars().all()

        if not accounts:
            print(f"  ⚠️  No active ad accounts found for {tenant_name}")
            return

        disabled_msg = f" ({len(disabled_count)} disabled)" if disabled_count else ""
        print(f"  📊 Found {len(accounts)} active ad accounts{disabled_msg}")

        # Get OAuth token for this tenant
        oauth_token = db.execute(
            select(models.OAuthToken).where(
                models.OAuthToken.tenant_id == UUID(tenant_id),
                models.OAuthToken.provider == "meta"
            )
        ).scalar_one_or_none()

        if not oauth_token:
            print(f"  ❌ No OAuth token found for {tenant_name}")
            return

        # Decrypt token
        fernet = Fernet(settings.TOKEN_ENCRYPTION_KEY.encode())
        access_token = fernet.decrypt(oauth_token.access_token).decode()

        # Check if token is expired
        if oauth_token.expires_at and oauth_token.expires_at < datetime.now(timezone.utc):
            print(f"  ⚠️  OAuth token expired for {tenant_name} (expired at {oauth_token.expires_at})")
            return

        # ⚡ PARALLÉLISATION avec Semaphore adaptatif
        # Commence avec MAX_CONCURRENT_ACCOUNTS, ajusté dynamiquement par rate_monitor
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_ACCOUNTS)

        print(f"  ⚡ Starting parallel refresh (max {MAX_CONCURRENT_ACCOUNTS} concurrent)...")

        # Créer les tâches parallèles (chaque tâche aura sa propre session DB)
        tasks = [
            refresh_single_account(
                account_id=account.id,
                account_fb_id=account.fb_account_id,
                account_name=account.name,
                tenant_id=tenant_id,
                semaphore=semaphore
            )
            for account in accounts
        ]

        # Exécuter en parallèle
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Compter les résultats
        success_count = 0
        error_count = 0

        for result in results:
            if isinstance(result, Exception):
                error_count += 1
                print(f"    ❌ Exception: {str(result)[:100]}")
            elif isinstance(result, tuple):
                success, msg = result
                if success:
                    success_count += 1
                else:
                    error_count += 1
                print(f"    {msg}")

        # Calculer le temps total
        elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()

        # Log le résumé du rate monitor
        from app.services.meta_client import meta_client
        print(f"  📊 Rate limit status: {meta_client.rate_monitor.get_usage_summary()}")

        print(f"  ✅ Tenant {tenant_name}: {success_count} success, {error_count} errors in {elapsed:.1f}s")

    except Exception as e:
        print(f"  ❌ Fatal error for tenant {tenant_name}: {e}")


async def main():
    """
    Main cron entry point
    Refresh tous les tenants actifs
    """
    print(f"🕐 Cron Refresh Started at {datetime.now(timezone.utc).isoformat()}")

    db = SessionLocal()

    try:
        # Get all tenants
        tenants = db.execute(select(models.Tenant)).scalars().all()

        if not tenants:
            print("⚠️  No tenants found")
            return

        print(f"📊 Found {len(tenants)} tenants to refresh")

        # Refresh each tenant sequentially
        for tenant in tenants:
            await refresh_tenant(str(tenant.id), tenant.name, db)

        print(f"\n✅ Cron Refresh Completed at {datetime.now(timezone.utc).isoformat()}")

    except Exception as e:
        print(f"❌ Fatal error in cron: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
