"""
Integration Test 1: Auth Cookie vs Bearer Token

Vérifie que l'API accepte l'authentification via:
1. Authorization: Bearer <token> header
2. HttpOnly cookie access_token

Critical pour sécurité: les deux méthodes doivent être supportées
"""
from uuid import uuid4
from fastapi.testclient import TestClient
from app.main import app
from app.utils.jwt import create_access_token
from app.database import get_db
from app import models
from sqlalchemy.orm import Session

client = TestClient(app)


def test_auth_with_bearer_token():
    """
    Test que l'API accepte un Bearer token dans l'Authorization header
    """
    # Créer un tenant et user de test
    db: Session = next(get_db())

    tenant = models.Tenant(
        name="Test Tenant Bearer",
        meta_user_id=f"test_bearer_{uuid4().hex[:8]}"
    )
    db.add(tenant)
    db.flush()

    user = models.User(
        tenant_id=tenant.id,
        name="Test User",
        email=f"test_bearer_{uuid4().hex[:8]}@example.com",
        meta_user_id=f"test_user_{uuid4().hex[:8]}"
    )
    db.add(user)
    db.commit()

    # Générer un JWT
    access_token = create_access_token(user_id=user.id, tenant_id=tenant.id)

    # Appeler /api/accounts/me avec Bearer token
    response = client.get(
        "/api/accounts/me",
        headers={"Authorization": f"Bearer {access_token}"}
    )

    # Vérifications
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == str(user.id)
    assert data["tenant_id"] == str(tenant.id)
    assert data["email"] == user.email

    # Cleanup
    db.delete(user)
    db.delete(tenant)
    db.commit()
    db.close()

    print("✅ Auth with Bearer token: PASSED")


def test_auth_with_cookie():
    """
    Test que l'API accepte un JWT dans un cookie HttpOnly
    """
    # Créer un tenant et user de test
    db: Session = next(get_db())

    tenant = models.Tenant(
        name="Test Tenant Cookie",
        meta_user_id=f"test_cookie_{uuid4().hex[:8]}"
    )
    db.add(tenant)
    db.flush()

    user = models.User(
        tenant_id=tenant.id,
        name="Test User",
        email=f"test_cookie_{uuid4().hex[:8]}@example.com",
        meta_user_id=f"test_user_{uuid4().hex[:8]}"
    )
    db.add(user)
    db.commit()

    # Générer un JWT
    access_token = create_access_token(user_id=user.id, tenant_id=tenant.id)

    # Appeler /api/accounts/me avec cookie
    response = client.get(
        "/api/accounts/me",
        cookies={"access_token": access_token}
    )

    # Vérifications
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == str(user.id)
    assert data["tenant_id"] == str(tenant.id)

    # Cleanup
    db.delete(user)
    db.delete(tenant)
    db.commit()
    db.close()

    print("✅ Auth with cookie: PASSED")


def test_auth_bearer_has_priority_over_cookie():
    """
    Test que si Bearer ET cookie sont présents, Bearer a priorité
    """
    # Créer 2 tenants/users
    db: Session = next(get_db())

    # Tenant 1 (pour Bearer)
    tenant1 = models.Tenant(
        name="Tenant Bearer",
        meta_user_id=f"test_priority_bearer_{uuid4().hex[:8]}"
    )
    db.add(tenant1)
    db.flush()

    user1 = models.User(
        tenant_id=tenant1.id,
        name="User Bearer",
        email=f"bearer_{uuid4().hex[:8]}@example.com",
        meta_user_id=f"user_bearer_{uuid4().hex[:8]}"
    )
    db.add(user1)
    db.flush()

    # Tenant 2 (pour Cookie)
    tenant2 = models.Tenant(
        name="Tenant Cookie",
        meta_user_id=f"test_priority_cookie_{uuid4().hex[:8]}"
    )
    db.add(tenant2)
    db.flush()

    user2 = models.User(
        tenant_id=tenant2.id,
        name="User Cookie",
        email=f"cookie_{uuid4().hex[:8]}@example.com",
        meta_user_id=f"user_cookie_{uuid4().hex[:8]}"
    )
    db.add(user2)
    db.commit()

    # Générer 2 JWTs différents
    token_bearer = create_access_token(user_id=user1.id, tenant_id=tenant1.id)
    token_cookie = create_access_token(user_id=user2.id, tenant_id=tenant2.id)

    # Appeler avec BOTH
    response = client.get(
        "/api/accounts/me",
        headers={"Authorization": f"Bearer {token_bearer}"},
        cookies={"access_token": token_cookie}
    )

    # Doit utiliser le Bearer (user1), pas le cookie (user2)
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == str(user1.id)
    assert data["tenant_id"] == str(tenant1.id)
    assert data["email"] == user1.email

    # Cleanup
    db.delete(user1)
    db.delete(user2)
    db.delete(tenant1)
    db.delete(tenant2)
    db.commit()
    db.close()

    print("✅ Bearer priority over cookie: PASSED")


if __name__ == "__main__":
    print("\n🧪 Running Auth Methods Integration Tests\n")
    test_auth_with_bearer_token()
    test_auth_with_cookie()
    test_auth_bearer_has_priority_over_cookie()
    print("\n✅ All auth tests PASSED!\n")
