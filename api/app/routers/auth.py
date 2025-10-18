"""
Router d'authentification Facebook OAuth avec state sécurisé
"""
from datetime import datetime, timedelta
import secrets
import time
from urllib.parse import urlencode
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert
from cryptography.fernet import Fernet

from ..database import get_db
from ..config import settings
from ..services.meta_client import meta_client, MetaAPIError
from ..utils.jwt import create_access_token
from .. import models

router = APIRouter(prefix="/facebook", tags=["auth"])

# Fernet pour chiffrement des tokens
fernet = Fernet(settings.TOKEN_ENCRYPTION_KEY.encode())


@router.get("/login")
async def facebook_login(request: Request):
    """
    Initie le flux OAuth Facebook
    Génère un state sécurisé et redirige vers Facebook
    """
    # Générer state sécurisé pour CSRF protection avec TTL
    state = secrets.token_urlsafe(32)
    request.session["oauth_state"] = {
        "value": state,
        "timestamp": int(time.time())
    }

    # Paramètres OAuth
    params = {
        "client_id": settings.META_APP_ID,
        "redirect_uri": settings.META_REDIRECT_URI,
        "response_type": "code",
        "state": state,
        "scope": "email,ads_read,public_profile",
    }

    # URL d'autorisation Facebook
    auth_url = f"https://www.facebook.com/{settings.META_API_VERSION}/dialog/oauth?{urlencode(params)}"

    return RedirectResponse(url=auth_url)


@router.get("/callback")
async def facebook_callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Callback OAuth Facebook
    Échange le code contre un token, récupère les ad accounts, et crée le tenant/user
    """
    # Gestion des erreurs OAuth
    if error:
        raise HTTPException(status_code=400, detail=f"OAuth error: {error}")

    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state parameter")

    # Vérification state (CSRF protection + TTL)
    state_data = request.session.get("oauth_state")
    if not state_data:
        raise HTTPException(status_code=403, detail="Invalid OAuth state (CSRF detected)")

    # Vérifier le state value
    expected_state = state_data.get("value") if isinstance(state_data, dict) else state_data
    if state != expected_state:
        request.session.pop("oauth_state", None)
        raise HTTPException(status_code=403, detail="Invalid OAuth state (CSRF detected)")

    # Vérifier TTL (10 minutes max)
    if isinstance(state_data, dict):
        timestamp = state_data.get("timestamp", 0)
        if int(time.time()) - timestamp > 600:  # 10 minutes
            request.session.pop("oauth_state", None)
            raise HTTPException(status_code=403, detail="Expired OAuth state (session timeout)")

    # Nettoyer le state de la session
    request.session.pop("oauth_state", None)

    try:
        # 1. Échanger code contre access token (long-lived, 60 jours)
        token_data = await meta_client.exchange_code_for_token(
            code=code,
            redirect_uri=settings.META_REDIRECT_URI
        )
        access_token = token_data["access_token"]
        expires_in = token_data.get("expires_in", 5184000)  # ~60 jours par défaut

        # 2. Récupérer métadonnées du token (user_id, scopes)
        token_info = await meta_client.debug_token(access_token)
        meta_user_id = token_info["user_id"]
        scopes = token_info.get("scopes", [])

        # Vérifier que le scope ads_read est présent
        if "ads_read" not in scopes:
            raise HTTPException(
                status_code=403,
                detail="Missing required scope: ads_read. Please re-authorize the application."
            )

        # 3. Récupérer infos utilisateur
        user_info = await meta_client.get_user_info(access_token, fields="id,name,email")
        user_name = user_info.get("name", "Unknown")
        user_email = user_info.get("email")

        # Normaliser email en minuscules + trim (pour l'index case-insensitive + CHECK constraint)
        if user_email:
            user_email = user_email.strip().lower()

        # 4. Récupérer ad accounts
        ad_accounts = await meta_client.get_ad_accounts(
            access_token,
            fields="id,name,currency,timezone_name,account_status"
        )

        # Chiffrer le token avant l'upsert
        token_encrypted = fernet.encrypt(access_token.encode()).decode()
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

        # 5. Transaction atomique : tenant → user → token → ad accounts
        with db.begin_nested():  # SAVEPOINT pour rollback partiel si erreur
            # 5a. Upsert tenant (ON CONFLICT DO UPDATE on meta_user_id)
            stmt = insert(models.Tenant).values(
                meta_user_id=meta_user_id,
                name=f"{user_name}'s Workspace",
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["meta_user_id"],
                set_={"name": stmt.excluded.name, "updated_at": func.now()},
            )
            db.execute(stmt)
            db.flush()

            # Récupérer le tenant créé/mis à jour
            tenant = db.execute(
                select(models.Tenant).where(models.Tenant.meta_user_id == meta_user_id)
            ).scalar_one()

            # 5b. Upsert user (ON CONFLICT DO UPDATE on tenant_id + meta_user_id)
            stmt = insert(models.User).values(
                tenant_id=tenant.id,
                meta_user_id=meta_user_id,
                email=user_email,
                name=user_name,
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

            # Récupérer le user créé/mis à jour
            user = db.execute(
                select(models.User).where(
                    models.User.tenant_id == tenant.id,
                    models.User.meta_user_id == meta_user_id
                )
            ).scalar_one()

            # 5c. Upsert OAuth token (ON CONFLICT DO UPDATE on user_id + provider)
            stmt = insert(models.OAuthToken).values(
                tenant_id=tenant.id,
                user_id=user.id,
                provider="meta",
                fb_user_id=meta_user_id,
                access_token=token_encrypted.encode(),
                expires_at=expires_at,
                scopes=scopes if isinstance(scopes, list) else [scopes],
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["user_id", "provider"],
                set_={
                    "access_token": stmt.excluded.access_token,
                    "expires_at": stmt.excluded.expires_at,
                    "scopes": stmt.excluded.scopes,
                    "fb_user_id": stmt.excluded.fb_user_id,
                },
            )
            db.execute(stmt)

            # 5d. Upsert ad accounts (ON CONFLICT DO UPDATE on tenant_id + fb_account_id)
            for account in ad_accounts:
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

            # 5e. Ensure tenant has a subscription (create FREE plan if none exists)
            existing_subscription = db.execute(
                select(models.Subscription).where(models.Subscription.tenant_id == tenant.id)
            ).scalar_one_or_none()

            if not existing_subscription:
                # Create default FREE plan subscription
                subscription = models.Subscription(
                    tenant_id=tenant.id,
                    plan="free",
                    status="active",
                    quota_accounts=3,  # Free tier: 3 accounts max
                    quota_refresh_per_day=1,  # Free tier: 1 refresh/day
                )
                db.add(subscription)

        # 6. Commit la transaction principale
        db.commit()

        # 7. Générer JWT access token pour l'API
        access_token = create_access_token(
            user_id=user.id,
            tenant_id=tenant.id
        )

        # 8. Redirect direct vers dashboard avec token (pas de page intermédiaire)
        redirect_url = f"{settings.DASHBOARD_URL}?token={access_token}&tenant_id={tenant.id}"
        response = RedirectResponse(url=redirect_url, status_code=302)

        # Poser le JWT dans un cookie HttpOnly sécurisé
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=not settings.DEBUG,  # HTTPS seulement en production
            samesite=settings.COOKIE_SAMESITE,  # "lax" for same eTLD+1, "none" for cross-site
            domain=settings.COOKIE_DOMAIN or None,  # None = current domain only
            max_age=30 * 60,  # 30 minutes
            path="/"
        )

        return response

    except MetaAPIError as e:
        raise HTTPException(status_code=502, detail=f"Meta API error: {str(e)}")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.post("/dev-login")
def dev_login(db: Session = Depends(get_db)):
    """
    DEBUG ONLY: Dev login endpoint to bypass OAuth for testing
    Creates/reuses a dev tenant and returns JWT token + cookie
    """
    if not settings.DEBUG:
        raise HTTPException(status_code=404, detail="Not found")

    # Get or create dev tenant
    tenant = db.execute(
        select(models.Tenant).where(models.Tenant.meta_user_id == "dev_tenant")
    ).scalar_one_or_none()

    if not tenant:
        tenant = models.Tenant(name="Dev Tenant", meta_user_id="dev_tenant")
        db.add(tenant)
        db.flush()

        # Create dev user
        user = models.User(
            tenant_id=tenant.id,
            meta_user_id="dev_user",
            email="dev@example.com",
            name="Dev User"
        )
        db.add(user)
        db.flush()

        # Create FREE subscription
        subscription = models.Subscription(
            tenant_id=tenant.id,
            plan="free",
            status="active",
            quota_accounts=3,
            quota_refresh_per_day=1
        )
        db.add(subscription)

        # Create dev ad account
        ad_account = models.AdAccount(
            tenant_id=tenant.id,
            fb_account_id="act_123456789",
            name="Dev Ad Account"
        )
        db.add(ad_account)

        db.commit()

    # Get user
    user = db.execute(
        select(models.User).where(
            models.User.tenant_id == tenant.id,
            models.User.meta_user_id == "dev_user"
        )
    ).scalar_one()

    # Create JWT token
    token = create_access_token(user.id, tenant.id)

    # Return JSON with token + set cookie
    resp = JSONResponse({
        "access_token": token,
        "tenant_id": str(tenant.id),
        "user_id": str(user.id),
        "message": "Dev login successful (DEBUG mode only)"
    })

    resp.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=not settings.DEBUG,
        samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN or None,
        max_age=30 * 60,  # 30 minutes
        path="/"
    )

    return resp


@router.post("/logout")
async def logout(request: Request):
    """Déconnexion (clear session)"""
    request.session.clear()
    return {"message": "Logged out successfully"}


@router.post("/test-token")
def test_token(tenant_id: str, db: Session = Depends(get_db)):
    """
    TEMPORARY: Generate JWT token for testing
    TODO: DELETE THIS ENDPOINT AFTER TESTING
    """
    from uuid import UUID

    # Validate tenant exists
    tenant = db.execute(
        select(models.Tenant).where(models.Tenant.id == UUID(tenant_id))
    ).scalar_one_or_none()

    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # Get user for this tenant
    user = db.execute(
        select(models.User).where(models.User.tenant_id == UUID(tenant_id))
    ).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found for tenant")

    user = user[0]

    # Generate token (7 days expiry)
    token = create_access_token(user.id, tenant.id, expires_delta=timedelta(days=7))

    return {
        "access_token": token,
        "tenant_id": str(tenant.id),
        "user_id": str(user.id),
        "message": "TEMPORARY test token - DELETE this endpoint after testing!"
    }
