# Insights

> Dashboard Meta Ads Analytics - Creative Testing

## URLs

| Composant | URL |
|-----------|-----|
| **Frontend** | https://insights.theaipipe.com |
| **Dashboard** | https://insights.theaipipe.com/index-saas.html |

## Infrastructure

| Composant | Où |
|-----------|-----|
| **API** | VPS Docker (port 10002) |
| **Database** | PostgreSQL sur VPS |
| **Storage** | Cloudflare R2 |
| **Frontend** | VPS `/var/www/insights` |
| **CI/CD** | GitHub Actions |

**VPS:** 66.135.5.31
**Repo GitHub:** creative-testing/insights

---

## Containers Docker

| Container | Description |
|-----------|-------------|
| `insights-api` | API FastAPI |
| `insights-cron` | Refresh automatique toutes les 2h |

**Logs cron:** `docker logs insights-cron`

---

## VPS Paths

| Chemin | Description |
|--------|-------------|
| `/root/insights-backend` | Code backend |
| `/var/www/insights` | Frontend statique |

---

## ⛔ RÈGLE CRITIQUE: PRODUCTION

**MASTER = PRODUCTION**

Push master → GitHub Actions déploie automatiquement sur VPS

### 🧪 OBLIGATOIRE après tout deploy
```bash
~/Documents/ProjetsDev/smoke-test.sh
```

---

## Deploy manuel

```bash
# Backend
ssh root@66.135.5.31 "cd /root/insights-backend && git pull origin master"
ssh root@66.135.5.31 "cd /root/insights-backend/api && docker compose -f docker-compose.prod.yml up -d --build"

# Frontend
ssh root@66.135.5.31 "cd /root/insights-backend && cp -r docs/* /var/www/insights/"
```

---

## Nginx Config

Fichier: `/etc/nginx/sites-enabled/insights.theaipipe.com`

```nginx
location / {
    root /var/www/insights;
    index index-landing.html index.html;
}

# OAuth callback
location /auth/facebook/callback {
    proxy_pass http://127.0.0.1:10002/auth/facebook/callback;
}

# API routes
location /api/ {
    proxy_pass http://127.0.0.1:10002/api/;
}
```

**⚠️ Piège:** Backend monte `/auth` (pas `/api/auth`), mais `/api/accounts` et `/api/data`.

---

## Pièges Courants

### Python Buffering (Docker)
```bash
# ✅ Logs en temps réel
docker exec -d container sh -c "PYTHONUNBUFFERED=1 python script.py"
```

### Enums PostgreSQL
```sql
-- ✅ Caster en text
WHERE status::text = 'ok'
```
