# Creative Testing SaaS API

Backend API FastAPI pour la version SaaS du Creative Testing Agent.

## 🚀 Quick Start

### 1. Installation

```bash
# Créer l'environnement virtuel
python3 -m venv venv
source venv/bin/activate  # ou `venv\Scripts\activate` sur Windows

# Installer les dépendances
pip install -r requirements-api.txt
pip install -r ../requirements.txt  # Dependencies partagées (requests, dotenv, etc.)
```

### 2. Configuration

```bash
# Copier .env.example vers .env
cp .env.example .env

# Générer une clé de chiffrement Fernet
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Éditer .env et remplir:
# - DATABASE_URL (Postgres)
# - META_APP_SECRET (après rotation!)
# - STRIPE_SECRET_KEY (test mode)
# - TOKEN_ENCRYPTION_KEY (clé générée ci-dessus)
# - etc.
```

### 3. Base de données

```bash
# Créer la première migration
alembic revision --autogenerate -m "Initial schema"

# Appliquer les migrations
alembic upgrade head
```

### 4. Lancer l'API

```bash
# Mode développement (avec reload)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

API disponible sur: http://localhost:8000
Docs interactive: http://localhost:8000/docs

## 📁 Structure

```
api/
├── alembic/                 # Migrations DB
├── app/
│   ├── main.py              # Point d'entrée FastAPI
│   ├── config.py            # Configuration (pydantic-settings)
│   ├── database.py          # SQLAlchemy setup
│   ├── models/              # Modèles SQLAlchemy
│   │   ├── tenant.py
│   │   ├── user.py
│   │   ├── subscription.py
│   │   ├── ad_account.py
│   │   ├── oauth_token.py
│   │   ├── refresh_job.py
│   │   └── naming_override.py
│   ├── schemas/             # Schémas Pydantic (TODO)
│   ├── routers/             # Routes API
│   │   ├── auth.py          # Facebook OAuth
│   │   ├── accounts.py      # Gestion comptes
│   │   ├── data.py          # Proxy données
│   │   └── billing.py       # Stripe
│   ├── services/            # Business logic (TODO)
│   └── utils/
│       └── security.py      # Chiffrement tokens
└── tests/                   # Tests (TODO)
```

## 🔒 Sécurité

### Secrets à NE JAMAIS commiter

- `.env`
- Tokens OAuth
- Clés Stripe
- Clés de chiffrement

### Rotation obligatoire (AVANT mise en prod)

❌ **App Secret Meta a été partagé dans Slack** → À régénérer immédiatement!

1. Aller sur https://developers.facebook.com/apps/1496103148207058/settings/basic/
2. "Reset App Secret"
3. Mettre le nouveau secret dans `.env` (jamais dans Git!)

### Chiffrement des tokens

Les tokens Facebook OAuth sont chiffrés en base avec Fernet (AES-128-CBC):

```python
from app.utils.security import encrypt_token, decrypt_token

# Avant stockage
encrypted = encrypt_token("EAABwz...")  # bytes

# Avant utilisation
token = decrypt_token(encrypted)  # str
```

## 📊 Base de données

### Modèle multi-tenant

```
Tenant (organisation cliente)
  ├── Users (avec rôles: owner, admin, manager, viewer)
  ├── Subscription (Stripe + quotas)
  ├── AdAccounts (comptes Meta connectés)
  ├── OAuthTokens (chiffrés)
  ├── RefreshJobs (historique fetch)
  └── NamingOverrides (corrections nomenclature)
```

### Migrations

```bash
# Créer une nouvelle migration
alembic revision --autogenerate -m "Description"

# Voir l'historique
alembic history

# Appliquer
alembic upgrade head

# Rollback
alembic downgrade -1
```

## 🎯 Endpoints (MVP)

### Auth
- `GET /auth/facebook/login` - Initie OAuth
- `GET /auth/facebook/callback` - Callback OAuth
- `POST /auth/logout` - Déconnexion

### Accounts
- `GET /api/accounts` - Liste comptes du tenant
- `POST /api/accounts/refresh/{id}` - Trigger refresh

### Data
- `GET /api/data/{account_id}/{period}` - Données optimisées

### Billing
- `POST /billing/create-checkout-session` - Stripe Checkout
- `POST /billing/webhook` - Stripe webhooks

## 🔗 Intégration avec le code existant

Le backend réutilise directement les scripts Python du repo:

```python
# api/app/services/fetch.py
from scripts.production.fetch_with_smart_limits import SmartMetaFetcher
from scripts.transform_to_columnar import transform_data
```

Pas de duplication de code! Monorepo architecture.

## 🧪 Tests

```bash
pytest
pytest --cov=app tests/
```

## 📝 TODO MVP

- [ ] Implémenter OAuth callback complet
- [ ] JWT pour sessions
- [ ] Background jobs (Redis + RQ)
- [ ] Storage R2/S3 client
- [ ] Schémas Pydantic
- [ ] Rate limiting par tenant
- [ ] Tests unitaires
- [ ] CI/CD

## 🚀 Déploiement

**Production actuelle : Vultr VPS** (66.135.5.31)
- Déploiement automatique via GitHub Actions (`.github/workflows/deploy-vps.yml`)
- Push sur `master` → rebuild Docker + copie frontend
- URL : `https://creative-testing.theaipipe.com`

Voir le guide de déploiement complet dans `../README_DEPLOY.md`.

## 📚 Docs

- [FastAPI](https://fastapi.tiangolo.com/)
- [SQLAlchemy](https://docs.sqlalchemy.org/)
- [Alembic](https://alembic.sqlalchemy.org/)
- [Stripe API](https://stripe.com/docs/api)
- [Meta Marketing API](https://developers.facebook.com/docs/marketing-apis)
