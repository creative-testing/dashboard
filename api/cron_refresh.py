#!/usr/bin/env python3
"""
🕐 Cron script pour refresh automatique de tous les tenants

Appelé toutes les 2h par Render Cron Job
Refresh les données Meta Ads de tous les tenants actifs
"""
import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Ajouter le répertoire parent au PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import select
from app.database import SessionLocal
from app import models
from app.models import JobStatus, RefreshJob
from app.services.refresher import MetaRefresher
from app.services.meta_client import meta_client
from cryptography.fernet import Fernet
from app.config import settings


async def refresh_tenant(tenant_id: str, tenant_name: str, db: SessionLocal):
    """
    Refresh tous les ad accounts d'un tenant

    Args:
        tenant_id: UUID du tenant
        tenant_name: Nom du tenant (pour logs)
        db: Session DB
    """
    from uuid import UUID

    print(f"\n🔄 Refreshing tenant: {tenant_name} ({tenant_id})")

    try:
        # Get all ad accounts for this tenant
        accounts = db.execute(
            select(models.AdAccount).where(models.AdAccount.tenant_id == UUID(tenant_id))
        ).scalars().all()

        if not accounts:
            print(f"  ⚠️  No ad accounts found for {tenant_name}")
            return

        print(f"  📊 Found {len(accounts)} ad accounts")

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

        # Check if token is expired (ne pas refresh si expiré)
        if oauth_token.expires_at and oauth_token.expires_at < datetime.utcnow():
            print(f"  ⚠️  OAuth token expired for {tenant_name} (expired at {oauth_token.expires_at})")
            return

        # Refresh each account sequentially (pour éviter rate limits)
        success_count = 0
        error_count = 0

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
                print(f"    ⏭️  Skipping {account.fb_account_id} ({account.name}) - already running")
                continue

            # Create job
            job = RefreshJob(
                tenant_id=UUID(tenant_id),
                ad_account_id=account.id,
                status=JobStatus.QUEUED
            )
            db.add(job)
            db.commit()
            db.refresh(job)

            # Execute refresh synchronously (pas de BackgroundTasks dans cron)
            try:
                print(f"    🔄 Refreshing {account.fb_account_id} ({account.name})...")

                # Update job status
                job.status = JobStatus.RUNNING
                job.started_at = datetime.utcnow()
                db.commit()

                # Run refresh
                refresher = MetaRefresher(access_token, account.fb_account_id, str(tenant_id))
                await refresher.refresh()

                # Mark job as completed
                job.status = JobStatus.COMPLETED
                job.completed_at = datetime.utcnow()
                db.commit()

                success_count += 1
                print(f"    ✅ Success: {account.fb_account_id}")

            except Exception as e:
                error_count += 1
                job.status = JobStatus.FAILED
                job.error = str(e)[:500]  # Limiter à 500 chars
                job.completed_at = datetime.utcnow()
                db.commit()
                print(f"    ❌ Error: {account.fb_account_id} - {str(e)[:100]}")

        print(f"  ✅ Tenant {tenant_name}: {success_count} success, {error_count} errors")

    except Exception as e:
        print(f"  ❌ Fatal error for tenant {tenant_name}: {e}")


async def main():
    """
    Main cron entry point
    Refresh tous les tenants actifs
    """
    print(f"🕐 Cron Refresh Started at {datetime.utcnow().isoformat()}")

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

        print(f"\n✅ Cron Refresh Completed at {datetime.utcnow().isoformat()}")

    except Exception as e:
        print(f"❌ Fatal error in cron: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
