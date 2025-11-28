#!/usr/bin/env python3
"""Test: 3 jours vs 90 jours fetch timing"""
import asyncio, time
from datetime import datetime, timedelta
from app.services.meta_client import meta_client
from app.database import SessionLocal
from app import models
from sqlalchemy import select
from cryptography.fernet import Fernet
from app.config import settings

async def test():
    db = SessionLocal()
    tenant = db.execute(select(models.Tenant).where(models.Tenant.name.like("%Fred%"))).scalar_one_or_none()
    oauth = db.execute(select(models.OAuthToken).where(models.OAuthToken.tenant_id == tenant.id)).scalar_one_or_none()
    fernet = Fernet(settings.TOKEN_ENCRYPTION_KEY.encode())
    token = fernet.decrypt(oauth.access_token).decode()
    account = db.execute(select(models.AdAccount).where(models.AdAccount.tenant_id == tenant.id)).scalars().first()
    print(f"Account: {account.fb_account_id}")
    until = datetime.now().strftime("%Y-%m-%d")

    since_3d = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
    t0 = time.time()
    d3 = await meta_client.get_insights(account.fb_account_id, token, since_3d, until)
    t3 = time.time() - t0

    since_90d = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
    t0 = time.time()
    d90 = await meta_client.get_insights(account.fb_account_id, token, since_90d, until)
    t90 = time.time() - t0

    print(f"3 jours:  {t3:.2f}s - {len(d3)} rows")
    print(f"90 jours: {t90:.2f}s - {len(d90)} rows")
    if t3 > 0:
        print(f"Ratio: {t90/t3:.1f}x")
    db.close()

if __name__ == "__main__":
    asyncio.run(test())
