# README_DEPLOY — SaaS MVP (Render + Cloudflare R2)

## Objectif
Déployer l'API FastAPI en HTTPS sur Render, avec OAuth Facebook et stockage R2. **Aucun impact** sur le dashboard prod des patrons (docs/index.html).

---

## 0) Prérequis rapides
- Compte **Render** (Web Service + PostgreSQL).
- Compte **Cloudflare R2** (ou S3 équivalent).
- App **Facebook** (mode Dév ok pour tests).

---

## 1) Render — Web Service API

**Service**
- Root dir: `api`
- Build: `pip install -r requirements-api.txt`
- Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

**Requirements**
Ajoutez `boto3` si absent dans `requirements-api.txt`:
```
boto3>=1.34
```

**Env Vars (minimum)**
```
ENVIRONMENT=production
DEBUG=false
API_VERSION=v1

# Secrets appli
SECRET_KEY=<32+ chars>
SESSION_SECRET=<32+ chars>
TOKEN_ENCRYPTION_KEY=<Fernet key base64>
JWT_ISSUER=creative-testing-api

# DB (Render Postgres)
DATABASE_URL=<render-postgres-url>

# OAuth Facebook (app de test ou de prod)
META_APP_ID=<facebook-app-id>
META_APP_SECRET=<facebook-app-secret>
META_API_VERSION=v23.0
META_REDIRECT_URI=https://creative-testing-api.onrender.com/auth/facebook/callback

# CORS & Cookies
ALLOWED_ORIGINS=https://creative-testing.github.io,https://creative-testing-api.onrender.com
COOKIE_SAMESITE=none
COOKIE_DOMAIN=

# Dashboard URL (pour la redirection post-callback)
DASHBOARD_URL=https://creative-testing.github.io/dashboard/index-mvp.html

# Storage: d'abord local, puis R2
STORAGE_MODE=local
LOCAL_DATA_ROOT=/tmp/data

# R2 (remplir quand on bascule)
STORAGE_ENDPOINT=
STORAGE_ACCESS_KEY=
STORAGE_SECRET_KEY=
STORAGE_BUCKET=creative-testing-data
STORAGE_REGION=auto

# Divers
RATE_LIMIT_PER_MINUTE=60
SENTRY_DSN=
```

Déployez. Vérifiez l'homepage:
```
curl -s https://creative-testing-api.onrender.com/  # 200 + JSON de service
```

---

## 2) Facebook App

Dans **Facebook Login → Settings**:
- **Valid OAuth Redirect URIs**:
  `https://creative-testing-api.onrender.com/auth/facebook/callback`
- (Optionnel pour Live) Privacy Policy URL + Terms of Service.

> **Switch d'app plus tard** (ex: "Ads‑Alchemy opt"): changez **uniquement** `META_APP_ID` et `META_APP_SECRET` sur Render. Pas de migration nécessaire.

---

## 3) Cloudflare R2 (après validation OAuth)

1. Créez un **bucket** (ex: `creative-testing-data`).
2. Générez des **API tokens** (Read/Write).
3. Renseignez dans Render:
```
STORAGE_MODE=r2
STORAGE_ENDPOINT=https://<account>.r2.cloudflarestorage.com
STORAGE_ACCESS_KEY=<...>
STORAGE_SECRET_KEY=<...>
STORAGE_BUCKET=creative-testing-data
STORAGE_REGION=auto
```
4. Redéployez.

**Vérification (facultative)**
```
# si vous utilisez awscli:
aws s3 ls --endpoint-url=$STORAGE_ENDPOINT s3://creative-testing-data/
```

---

## 4) Tests E2E (prod‑like)

1. **Login OAuth**
   - Ouvrir `https://creative-testing-api.onrender.com/auth/facebook/login`
   - Consent
   - Redirection vers : `DASHBOARD_URL?token=&tenant_id=...`
   - UI: "Estado: Conectado"

2. **Refresh Data**
   - Bouton **Actualizar Datos**
   - Attendu: popup succès & `Última actualización` mise à jour

3. **Data API**
   - `GET /api/data/files/{act_id}/data/optimized/manifest.json` → 200
   - `{meta,agg,summary}.json` présents

4. **FE error surfacing (mode dev‑login)**
   - en local (DEBUG=true): 400 clair `"No OAuth token found..."`.

---

## 5) Rollback

- Problème R2 → `STORAGE_MODE=local` puis redeploy.
- Redirection → changer `DASHBOARD_URL`.
- **Aucun** effet sur `docs/index.html` (prod patrons).

---

## 6) Sécurité

- Tokens OAuth chiffrés (Fernet).
- JWT `iss/aud` vérifiés.
- CORS réduit à GH Pages + Render.
- Clé R2 avec droits minimes (bucket scope).
- Pas de secrets commités (variables d'environnement uniquement).

---

## 7) Notes d'archi

- Chemins de stockage:
```
tenants/{tenant_id}/accounts/{act_id}/data/optimized/
├─ meta_v1.json
├─ agg_v1.json
├─ summary_v1.json
└─ manifest.json
```
- Endpoint data (auth requis):
```
GET /api/data/files/{act_id}/{filename}
```
- Fenêtre de fetch: **30 jours (J‑30 → J‑1)** en daily (`time_increment=1`).

---

## 8) Checklist Go‑Live (5 minutes)

- [ ] Homepage API 200
- [ ] OAuth OK (redirection vers GH Pages)
- [ ] Refresh OK (agg/meta/summary/manifest)
- [ ] R2 activé (optionnel) et listé
- [ ] Patrons: `docs/index.html` inchangé

---

## 9) Switch futur vers l'app Facebook "Ads‑Alchemy opt"

Quand tes patrons veulent passer sur **leur** app:

1. Dans Render, remplace **uniquement**:
```
META_APP_ID=1496103148207058
META_APP_SECRET=<secret de Ads-Alchemy opt>
```

2. Vérifie que `Valid OAuth Redirect URIs` contient bien:
```
https://creative-testing-api.onrender.com/auth/facebook/callback
```

> Aucune migration à faire. Les tenants restent isolés par `tenant_id`, le user est identifié par Meta, et le pipeline reste identique.
