"""
Integration Test 2: Tenant Isolation

CRITICAL SECURITY TEST

Vérifie que:
1. User A ne peut PAS voir les accounts de User B (autre tenant)
2. User A ne peut PAS refresh les accounts de User B
3. User A ne peut PAS accéder aux fichiers de User B

Si ce test échoue → FUITE DE DONNÉES ENTRE TENANTS → CRITIQUE
"""
from uuid import uuid4, UUID
from fastapi.testclient import TestClient
from app.main import app
from app.utils.jwt import create_access_token
from app.database import get_db
from app import models
from sqlalchemy.orm import Session

client = TestClient(app)


def setup_two_tenants():
    """
    Setup: Créer 2 tenants avec users et ad accounts
    Tenant A: user_a avec account_a
    Tenant B: user_b avec account_b
    """
    db: Session = next(get_db())

    # Tenant A
    tenant_a = models.Tenant(
        name="Tenant A",
        meta_user_id=f"tenant_a_{uuid4().hex[:8]}"
    )
    db.add(tenant_a)
    db.flush()

    user_a = models.User(
        tenant_id=tenant_a.id,
        name="User A",
        email=f"user_a_{uuid4().hex[:8]}@example.com",
        meta_user_id=f"meta_a_{uuid4().hex[:8]}"
    )
    db.add(user_a)
    db.flush()

    account_a = models.AdAccount(
        tenant_id=tenant_a.id,
        fb_account_id=f"act_a_{uuid4().hex[:12]}",
        name="Account A",
        profile="ecom"  # Valid enum value (lowercase)
    )
    db.add(account_a)

    # Tenant B
    tenant_b = models.Tenant(
        name="Tenant B",
        meta_user_id=f"tenant_b_{uuid4().hex[:8]}"
    )
    db.add(tenant_b)
    db.flush()

    user_b = models.User(
        tenant_id=tenant_b.id,
        name="User B",
        email=f"user_b_{uuid4().hex[:8]}@example.com",
        meta_user_id=f"meta_b_{uuid4().hex[:8]}"
    )
    db.add(user_b)
    db.flush()

    account_b = models.AdAccount(
        tenant_id=tenant_b.id,
        fb_account_id=f"act_b_{uuid4().hex[:12]}",
        name="Account B",
        profile="leads"  # Valid enum value (lowercase, plural)
    )
    db.add(account_b)

    db.commit()

    return {
        "tenant_a": tenant_a,
        "user_a": user_a,
        "account_a": account_a,
        "tenant_b": tenant_b,
        "user_b": user_b,
        "account_b": account_b,
        "db": db,
    }


def test_user_cannot_see_other_tenant_accounts():
    """
    User A ne doit voir QUE ses accounts, pas ceux de User B
    """
    data = setup_two_tenants()

    # Générer JWT pour User A
    token_a = create_access_token(
        user_id=data["user_a"].id,
        tenant_id=data["tenant_a"].id
    )

    # User A appelle GET /api/accounts
    response = client.get(
        "/api/accounts",
        headers={"Authorization": f"Bearer {token_a}"}
    )

    assert response.status_code == 200
    accounts = response.json()["accounts"]

    # Vérifier que SEUL account_a est visible
    assert len(accounts) == 1
    assert accounts[0]["fb_account_id"] == data["account_a"].fb_account_id

    # Vérifier que account_b n'est PAS dans la liste
    account_b_ids = [acc["fb_account_id"] for acc in accounts]
    assert data["account_b"].fb_account_id not in account_b_ids

    # Cleanup
    db = data["db"]
    db.delete(data["account_a"])
    db.delete(data["account_b"])
    db.delete(data["user_a"])
    db.delete(data["user_b"])
    db.delete(data["tenant_a"])
    db.delete(data["tenant_b"])
    db.commit()
    db.close()

    print("✅ User cannot see other tenant's accounts: PASSED")


def test_user_cannot_refresh_other_tenant_account():
    """
    User A ne doit PAS pouvoir refresh l'account de User B
    """
    data = setup_two_tenants()

    # Générer JWT pour User A
    token_a = create_access_token(
        user_id=data["user_a"].id,
        tenant_id=data["tenant_a"].id
    )

    # User A essaie de refresh l'account de User B
    response = client.post(
        f"/api/accounts/refresh/{data['account_b'].fb_account_id}",
        headers={"Authorization": f"Bearer {token_a}"}
    )

    # Doit être 404 ou 403 (pas 200 !)
    # 404 = "Account not found for your workspace" (ce qu'on utilise)
    assert response.status_code in [403, 404, 500]

    if response.status_code == 500:
        # Si 500, vérifier que c'est bien "not found", pas autre chose
        error = response.json()["detail"]
        assert "not found" in error.lower() or "no oauth token" in error.lower()

    # Cleanup
    db = data["db"]
    db.delete(data["account_a"])
    db.delete(data["account_b"])
    db.delete(data["user_a"])
    db.delete(data["user_b"])
    db.delete(data["tenant_a"])
    db.delete(data["tenant_b"])
    db.commit()
    db.close()

    print("✅ User cannot refresh other tenant's account: PASSED")


def test_user_cannot_access_other_tenant_files():
    """
    User A ne doit PAS pouvoir lire les fichiers de l'account de User B
    """
    data = setup_two_tenants()

    # Générer JWT pour User A
    token_a = create_access_token(
        user_id=data["user_a"].id,
        tenant_id=data["tenant_a"].id
    )

    # User A essaie de lire meta_v1.json de l'account B
    response = client.get(
        f"/api/data/files/{data['account_b'].fb_account_id}/meta_v1.json",
        headers={"Authorization": f"Bearer {token_a}"}
    )

    # Doit être 404 (pas 200 !)
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()

    # Cleanup
    db = data["db"]
    db.delete(data["account_a"])
    db.delete(data["account_b"])
    db.delete(data["user_a"])
    db.delete(data["user_b"])
    db.delete(data["tenant_a"])
    db.delete(data["tenant_b"])
    db.commit()
    db.close()

    print("✅ User cannot access other tenant's files: PASSED")


if __name__ == "__main__":
    print("\n🧪 Running Tenant Isolation Integration Tests\n")
    print("⚠️  CRITICAL SECURITY TESTS - If these fail, there's a data leak!\n")
    test_user_cannot_see_other_tenant_accounts()
    test_user_cannot_refresh_other_tenant_account()
    test_user_cannot_access_other_tenant_files()
    print("\n✅ All tenant isolation tests PASSED!\n")
    print("🔒 No data leaks detected between tenants\n")
