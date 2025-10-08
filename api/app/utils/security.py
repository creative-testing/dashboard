"""
Utilitaires de sécurité : chiffrement des tokens OAuth
⚠️ CRITIQUE : Les tokens Facebook doivent être chiffrés en base

Utilise MultiFernet pour permettre la rotation des clés de chiffrement sans casser
les tokens existants. La clé primaire chiffre les nouveaux tokens, les anciennes
clés permettent de déchiffrer les tokens existants.
"""
from cryptography.fernet import Fernet, MultiFernet
from typing import List
from ..config import settings


def get_fernet() -> MultiFernet:
    """
    Retourne une instance MultiFernet pour chiffrement/déchiffrement avec rotation

    MultiFernet essaye les clés dans l'ordre :
    1. Chiffre toujours avec la clé primaire (première clé)
    2. Déchiffre avec n'importe quelle clé de la liste (permet rotation)

    Configuration dans .env:
    - FERNET_PRIMARY_KEY: Clé actuelle (utilisée pour chiffrer)
    - FERNET_OLD_KEYS: Anciennes clés séparées par virgule (pour déchiffrer)
    """
    keys: List[bytes] = []

    # Clé primaire (obligatoire)
    if not settings.TOKEN_ENCRYPTION_KEY:
        raise RuntimeError("FERNET_PRIMARY_KEY not configured in .env")
    keys.append(settings.TOKEN_ENCRYPTION_KEY.encode())

    # Anciennes clés (optionnel, pour rotation)
    old_keys = getattr(settings, 'FERNET_OLD_KEYS', '')
    if old_keys:
        for key in old_keys.split(','):
            key = key.strip()
            if key:
                keys.append(key.encode())

    # Créer MultiFernet avec toutes les clés
    fernets = [Fernet(k) for k in keys]
    return MultiFernet(fernets)


def encrypt_token(token: str) -> bytes:
    """
    Chiffre un token OAuth avant stockage en DB

    Args:
        token: Token en clair (string)

    Returns:
        bytes: Token chiffré (à stocker en bytea)
    """
    f = get_fernet()
    return f.encrypt(token.encode())


def decrypt_token(encrypted_token: bytes) -> str:
    """
    Déchiffre un token depuis la DB

    Args:
        encrypted_token: Token chiffré (bytes depuis DB)

    Returns:
        str: Token en clair
    """
    f = get_fernet()
    return f.decrypt(encrypted_token).decode()


def generate_encryption_key() -> str:
    """
    Génère une nouvelle clé de chiffrement Fernet
    À utiliser UNE SEULE FOIS pour créer TOKEN_ENCRYPTION_KEY

    Returns:
        str: Clé Fernet (à mettre dans .env)
    """
    return Fernet.generate_key().decode()


# Helper pour générer la clé
if __name__ == "__main__":
    print("Nouvelle clé de chiffrement Fernet:")
    print(generate_encryption_key())
    print("\nAjoutez cette clé dans .env comme TOKEN_ENCRYPTION_KEY")
