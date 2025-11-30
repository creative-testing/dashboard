# Notes Pipeline Meta Ads - CLAUDE

> **🔴 DB: VPS PostgreSQL** — PAS Supabase (Supabase c'est agente-creativo-ia)

## ☁️ INFRA CLOUD (Ce projet spécifiquement)

| Composant | Où | Accès |
|-----------|-----|-------|
| **API SaaS** | VPS (via GitHub Secrets `VPS_HOST`) | `https://creative-testing.theaipipe.com` |
| **Database** | PostgreSQL sur le même VPS | `DATABASE_URL` env var |
| **Storage** | Cloudflare R2 | `STORAGE_*` env vars |
| **Frontend** | GitHub Pages | `https://creative-testing.github.io/dashboard/` |
| **CI/CD** | GitHub Actions | `.github/workflows/deploy-vps.yml` |

**⚠️ Ce n'est PAS le VPS Vultr 66.135.5.31** (celui-là c'est dental-portal/agente)
**⚠️ Ce n'est PAS Supabase** (celui du MCP c'est agente-creativo-ia)

**Logs cron** : `docker logs creative-testing-cron` sur le VPS

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

## 🏗️ ARCHITECTURE SAAS (Nov 2025)

```
Frontend (GitHub Pages)
├── index-landing.html          # Landing page
├── index-saas.html             # Dashboard SaaS
├── oauth-callback.html         # OAuth callback
├── data_loader_saas.js         # Chargement données API
└── data_adapter.js             # Conversion format columnar

API VPS (FastAPI + Docker)
├── /api/auth/facebook/*        # OAuth Facebook
├── /api/accounts/*             # Gestion comptes Meta
├── /api/data/*                 # Données (proxy R2)
├── /api/data/demographics/*    # Données démographiques
└── /api/health                 # Health check

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
