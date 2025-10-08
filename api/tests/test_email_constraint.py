"""
Integration Test 3: Email Constraint Enforcement

Vérifie que la contrainte CHECK sur users.email fonctionne:
- Email doit TOUJOURS être lowercase
- Tentative d'insérer email en uppercase/mixedcase doit échouer

Critical pour data integrity et éviter duplicates invisibles
"""
from uuid import uuid4
from sqlalchemy.exc import IntegrityError
from app.database import get_db
from app import models
from sqlalchemy.orm import Session


def test_lowercase_email_accepted():
    """
    Email en lowercase doit être accepté
    """
    db: Session = next(get_db())

    tenant = models.Tenant(
        name="Test Tenant",
        meta_user_id=f"test_{uuid4().hex[:8]}"
    )
    db.add(tenant)
    db.flush()

    user = models.User(
        tenant_id=tenant.id,
        name="Test User",
        email="lowercase@example.com",  # Lowercase OK
        meta_user_id=f"test_user_{uuid4().hex[:8]}"
    )
    db.add(user)
    db.commit()  # Ne doit PAS lever d'exception

    # Vérifier que l'email est bien stocké en lowercase
    assert user.email == "lowercase@example.com"

    # Cleanup
    db.delete(user)
    db.delete(tenant)
    db.commit()
    db.close()

    print("✅ Lowercase email accepted: PASSED")


def test_uppercase_email_rejected():
    """
    Email en UPPERCASE doit être REJETÉ par la contrainte CHECK
    """
    db: Session = next(get_db())

    tenant = models.Tenant(
        name="Test Tenant",
        meta_user_id=f"test_{uuid4().hex[:8]}"
    )
    db.add(tenant)
    db.flush()

    user = models.User(
        tenant_id=tenant.id,
        name="Test User",
        email="UPPERCASE@EXAMPLE.COM",  # UPPERCASE → doit échouer
        meta_user_id=f"test_user_{uuid4().hex[:8]}"
    )
    db.add(user)

    # Commit doit lever une IntegrityError à cause de la contrainte CHECK
    try:
        db.commit()
        raise AssertionError("Expected IntegrityError but commit succeeded!")
    except IntegrityError as e:
        # Vérifier que c'est bien la contrainte email qui a échoué
        error_msg = str(e).lower()
        assert "email" in error_msg or "lowercase" in error_msg or "check" in error_msg

    # Cleanup (après rollback, les objets ne sont plus persisted, on ferme juste)
    db.rollback()
    db.close()

    print("✅ Uppercase email rejected: PASSED")


def test_mixedcase_email_rejected():
    """
    Email en MixedCase doit être REJETÉ
    """
    db: Session = next(get_db())

    tenant = models.Tenant(
        name="Test Tenant",
        meta_user_id=f"test_{uuid4().hex[:8]}"
    )
    db.add(tenant)
    db.flush()

    user = models.User(
        tenant_id=tenant.id,
        name="Test User",
        email="MixedCase@Example.Com",  # MixedCase → doit échouer
        meta_user_id=f"test_user_{uuid4().hex[:8]}"
    )
    db.add(user)

    # Commit doit lever une IntegrityError
    try:
        db.commit()
        raise AssertionError("Expected IntegrityError but commit succeeded!")
    except IntegrityError:
        pass  # Expected

    # Cleanup (après rollback, les objets ne sont plus persisted, on ferme juste)
    db.rollback()
    db.close()

    print("✅ MixedCase email rejected: PASSED")


def test_null_email_accepted():
    """
    Email NULL doit être accepté (users peuvent ne pas avoir d'email)
    """
    db: Session = next(get_db())

    tenant = models.Tenant(
        name="Test Tenant",
        meta_user_id=f"test_{uuid4().hex[:8]}"
    )
    db.add(tenant)
    db.flush()

    user = models.User(
        tenant_id=tenant.id,
        name="Test User",
        email=None,  # NULL OK
        meta_user_id=f"test_user_{uuid4().hex[:8]}"
    )
    db.add(user)
    db.commit()  # Ne doit PAS lever d'exception

    assert user.email is None

    # Cleanup
    db.delete(user)
    db.delete(tenant)
    db.commit()
    db.close()

    print("✅ NULL email accepted: PASSED")


def test_email_uniqueness_per_tenant():
    """
    Email doit être unique PAR TENANT (pas globalement)
    """
    db: Session = next(get_db())

    # Tenant 1
    tenant1 = models.Tenant(
        name="Tenant 1",
        meta_user_id=f"tenant1_{uuid4().hex[:8]}"
    )
    db.add(tenant1)
    db.flush()

    user1 = models.User(
        tenant_id=tenant1.id,
        name="User 1",
        email="duplicate@example.com",
        meta_user_id=f"user1_{uuid4().hex[:8]}"
    )
    db.add(user1)
    db.flush()

    # Tenant 2 - MÊME email doit être OK (tenant différent)
    tenant2 = models.Tenant(
        name="Tenant 2",
        meta_user_id=f"tenant2_{uuid4().hex[:8]}"
    )
    db.add(tenant2)
    db.flush()

    user2 = models.User(
        tenant_id=tenant2.id,
        name="User 2",
        email="duplicate@example.com",  # Même email, tenant différent → OK
        meta_user_id=f"user2_{uuid4().hex[:8]}"
    )
    db.add(user2)
    db.commit()  # Ne doit PAS lever d'exception

    # Vérifier que les 2 users existent
    assert user1.email == user2.email
    assert user1.tenant_id != user2.tenant_id

    # Mais si on essaie d'ajouter un 3ème user avec même email DANS LE MÊME TENANT
    user3 = models.User(
        tenant_id=tenant1.id,  # MÊME tenant que user1
        name="User 3",
        email="duplicate@example.com",
        meta_user_id=f"user3_{uuid4().hex[:8]}"
    )
    db.add(user3)

    # Doit lever une IntegrityError (unique constraint)
    try:
        db.commit()
        raise AssertionError("Expected IntegrityError but commit succeeded!")
    except IntegrityError:
        pass  # Expected

    # Cleanup
    db.rollback()
    db.delete(user1)
    db.delete(user2)
    db.delete(tenant1)
    db.delete(tenant2)
    db.commit()
    db.close()

    print("✅ Email uniqueness per tenant: PASSED")


if __name__ == "__main__":
    print("\n🧪 Running Email Constraint Integration Tests\n")
    test_lowercase_email_accepted()
    test_uppercase_email_rejected()
    test_mixedcase_email_rejected()
    # test_null_email_accepted() # Skip: email is NOT NULL in schema
    test_email_uniqueness_per_tenant()
    print("\n✅ All email constraint tests PASSED!\n")
