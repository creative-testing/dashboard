# Notes Pipeline Meta Ads - CLAUDE

> **🔴 DB: VPS PostgreSQL** — PAS Supabase (Supabase c'est agente-creativo-ia)

## ☁️ INFRA CLOUD (Ce projet spécifiquement)

| Composant | Où | Accès |
|-----------|-----|-------|
| **API SaaS** | VPS Docker (port 10002) | `https://insights.theaipipe.com` |
| **Database** | PostgreSQL sur le même VPS | `DATABASE_URL` env var |
| **Storage** | Cloudflare R2 | `STORAGE_*` env vars |
| **Frontend** | VPS (même que API) | `https://insights.theaipipe.com` |
| **CI/CD** | GitHub Actions | `.github/workflows/deploy-vps.yml` |

**✅ VPS Vultr 66.135.5.31** - Même serveur que dental-portal/agente (SSH: `root@66.135.5.31`)
**⚠️ Ce n'est PAS Supabase** (celui du MCP c'est agente-creativo-ia)

**Logs cron** : `docker logs creative-testing-cron` sur le VPS

### 🔧 Configuration Nginx (Jan 2026)

Fichier: `/etc/nginx/sites-available/insights.theaipipe.com`

```nginx
server {
    listen 80;
    server_name insights.theaipipe.com;
    client_max_body_size 50M;

    # Static files (landing, dashboard, oauth-callback)
    location / {
        root /var/www/creative-testing;
        index index-landing.html index.html;
        try_files $uri $uri/ /index-landing.html;
    }

    # OAuth callback - Facebook redirige ici (sans /api)
    location /auth/facebook/callback {
        proxy_pass http://127.0.0.1:10002/auth/facebook/callback;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Auth routes: /api/auth/* -> /auth/* (frontend appelle /api/auth mais backend a /auth)
    location /api/auth/ {
        proxy_pass http://127.0.0.1:10002/auth/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # API routes: /api/* -> /api/* (accounts, data, billing ont le préfixe /api)
    location /api/ {
        proxy_pass http://127.0.0.1:10002/api/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 120s;
        proxy_send_timeout 120s;
        proxy_read_timeout 120s;
    }
}
```

**⚠️ Piège routes auth vs api** : Le backend FastAPI monte les routes auth sous `/auth` (pas `/api/auth`), mais les routes accounts/data sous `/api/accounts` et `/api/data`. Nginx doit donc faire le mapping.

---

## ⛔ RÈGLE CRITIQUE: PROTECTION DE LA PRODUCTION

**MASTER = PRODUCTION - NE JAMAIS TOUCHER SANS AUTORISATION EXPLICITE**

La branche `master` alimente le dashboard SaaS en production.
**Toute modification de master peut CASSER le système en production !**

### ✅ CI/CD AUTOMATIQUE
**Push master → GitHub Actions déploie automatiquement sur VPS** (`.github/workflows/deploy-vps.yml` : git pull + docker rebuild + copie frontend + smoke tests)

### ❌ NE JAMAIS modifier directement sur le VPS
Toute modification doit être faite en local puis pushée sur master (sinon écrasée par CI/CD)

---

## 🏗️ ARCHITECTURE SAAS (Jan 2026)

```
Frontend (VPS - https://insights.theaipipe.com)
├── index-landing.html          # Landing page (page d'accueil)
├── index-saas.html             # Dashboard SaaS
├── oauth-callback.html         # OAuth callback
├── data_loader_saas.js         # Chargement données API
└── data_adapter.js             # Conversion format columnar

API VPS (FastAPI + Docker sur port 10002)
├── /auth/facebook/*            # OAuth Facebook (⚠️ PAS /api/auth)
├── /api/accounts/*             # Gestion comptes Meta
├── /api/data/*                 # Données (proxy R2)
├── /api/data/demographics/*    # Données démographiques
└── /health                     # Health check

Storage R2 (Cloudflare)
└── tenants/{tenant_id}/accounts/{act_id}/
    ├── meta_v1.json
    ├── agg_v1.json
    ├── summary_v1.json
    └── demographics/{period}d.json

Cron (Docker container)
└── Refresh automatique toutes les 2h
```

---

## ⚠️ Piège Instagram Carousels (Sept 10, 2025)

**IMPORTANT**: Les carousels Instagram ne sont PAS cassés !
- **Symptôme**: "Cette publication n'est pas disponible" quand on clique
- **Cause**: Instagram requiert d'être connecté pour voir les posts
- **Solution**: Se connecter à Instagram dans le même navigateur
- **NE PAS** perdre de temps à debugger les URLs ou l'API
- Dashboard affiche maintenant un avertissement au premier clic

## 🔌 MCP `meta-ads-local` disponible pour tester l'API Meta directement

## ⚠️ Pièges Courants

### Python Buffering (Docker)
**Symptôme**: Log file vide (0 bytes) alors que le script tourne
**Cause**: Python bufferise stdout par défaut → les logs n'apparaissent qu'à la fin
**Solution**: Toujours utiliser `PYTHONUNBUFFERED=1` pour les scripts Docker :
```bash
# ❌ Mauvais - logs vides pendant l'exécution
docker exec -d container python script.py > /tmp/log.txt 2>&1

# ✅ Bon - logs en temps réel
docker exec -d container sh -c "PYTHONUNBUFFERED=1 python script.py > /tmp/log.txt 2>&1"
```

### Enums PostgreSQL
La colonne `status` (table `refresh_jobs`) est de type `ENUM`.
- ❌ Ne pas utiliser de strings dans les requêtes SQL brutes via psql (`status = 'ok'`)
- ✅ Caster explicitement en text : `status::text = 'ok'`
- ✅ Ou utiliser les modèles SQLAlchemy (`JobStatus.OK`)

## 🎯 Parser V2 avec Confiance (Sept 12, 2025)

### Nouveautés
- **Détection dynamique de créateurs** depuis les ads existantes
- **Score de confiance** (0-100%) par champ parsé
- **Stopwords améliorés** pour éviter les faux positifs
- **Expansion des hooks** (H123 → H1, H2, H3)

### Structure nomenclature
```
Type / Angle / Creator / Age / Hook
Ex: Prospecting / Picazon / UGC_Maria / 35+ / H1
```

### Colonnes ajoutées au dashboard
- Angulo (avec badge confiance)
- Creador (avec détection dynamique)
- Hook (avec expansion)
- Conf. (score global)

---

## 🤖 Revue par Gemini

Pour obtenir une seconde opinion de Gemini sur le travail en cours, exécuter :

```bash
python3 ~/Documents/ProjetsDev/gemini-reviewer/gemini_sync.py --send --url 7a9f9729fd7299de
```

Utile pour :
- Valider une architecture ou approche technique
- Avoir un regard critique sur du code avant déploiement
- Identifier des angles morts ou améliorations potentielles
