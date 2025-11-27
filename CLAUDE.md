# Notes Pipeline Meta Ads - CLAUDE

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

**Logs cron** : GitHub Actions ou `docker logs creative-testing-cron` sur le VPS

---

## ⛔ RÈGLE CRITIQUE: PROTECTION DE LA PRODUCTION

**MASTER = PRODUCTION - NE JAMAIS TOUCHER SANS AUTORISATION EXPLICITE**

La branche `master` alimente le dashboard de production utilisé par l'entreprise et les patrons de Frederic.
**Toute modification de master peut CASSER le système en production !**

### ✅ CI/CD AUTOMATIQUE (Oct 30, 2025)
**Push master → GitHub Actions déploie automatiquement sur VPS Vultr** (`.github/workflows/deploy-vps.yml` : git pull + docker rebuild + copie frontend)

### ❌ NE JAMAIS modifier directement sur le VPS
Toute modification doit être faite en local puis pushée sur master (sinon écrasée par CI/CD)

---

## 🛡️ COEXISTENCE DASHBOARD PRODUCTION & SAAS (Oct 15, 2025)

### CONTEXTE CRITIQUE

Le dashboard de production fonctionne actuellement pour les patrons de Frederic :
- **URL en production** : https://creative-testing.github.io/dashboard/index_full.html
- **Fichier** : `docs/index_full.html`
- **Données** : `docs/data/optimized/*.json` (générés par GitHub Actions)
- **Pipeline** : `.github/workflows/refresh-data.yml` → `fetch_with_smart_limits.py` → `transform_to_columnar.py`

### ⚠️ RÈGLES DE COEXISTENCE

**NE JAMAIS TOUCHER** :
- ❌ `docs/index_full.html` (dashboard actuel des patrons)
- ❌ `docs/data/optimized/*.json` (données actuelles)
- ❌ `.github/workflows/refresh-data.yml` (pipeline de données actuel)
- ❌ Tout fichier qui pourrait affecter index_full.html

**NOUVEAU DASHBOARD SAAS** :
- ✅ `docs/oauth-callback.html` (page callback OAuth)
- ✅ API VPS : `creative-testing.theaipipe.com` (Vultr, déploiement auto via CI/CD)
- ✅ Données isolées par tenant : `tenants/{tenant_id}/accounts/{act_id}/...`
- ✅ Authentification OAuth Facebook

### ARCHITECTURE PARALLÈLE

```
PRODUCTION (Patrons)                     SAAS (Nouveaux utilisateurs)
├── index_full.html                      ├── oauth-callback.html
├── GitHub Actions refresh               ├── API VPS (Vultr)
├── Token hardcodé dans secrets          ├── OAuth Facebook
├── Données globales                     ├── Données par tenant
└── docs/data/optimized/*.json           └── tenants/{tenant}/accounts/{act}/*.json
```

### WORKFLOW DE DÉPLOIEMENT SÉCURISÉ

1. **Développement** : Toujours sur `saas-mvp`
2. **Tests locaux** : `http://localhost:8080/oauth-callback.html`
3. **Publication** : PR séparée qui ajoute UNIQUEMENT les fichiers SaaS nécessaires
4. **Vérification** : Confirmer qu'aucun fichier existant n'est modifié
5. **Validation** : L'URL des patrons doit rester fonctionnelle après merge

### CHECKLIST AVANT TOUT MERGE VERS MASTER

- [ ] `docs/index_full.html` n'est PAS modifié
- [ ] `docs/data/optimized/*` n'est PAS modifié
- [ ] `.github/workflows/refresh-data.yml` n'est PAS modifié
- [ ] Test manuel de https://creative-testing.github.io/dashboard/index_full.html
- [ ] La PR ajoute UNIQUEMENT des nouveaux fichiers SaaS

---

## 🚨 Problèmes résolus (Sept 2, 2025)

### 1. Date affichée incorrecte
**Problème**: Dashboard affichait "02/09/2025 (cargando datos...)" mais données du 31/08
**Cause**: UI cherchait `ad.date_start` qui n'existe pas dans les données optimisées
**Fix**: 
- Ajouté `data_min_date` et `data_max_date` dans `transform_to_columnar.py`
- UI utilise maintenant `data_max_date` depuis les métadonnées

### 2. Fetch ne lançait pas transform automatiquement
**Problème**: Erreur "cannot access local variable 'sys'"
**Cause**: `sys` non importé dans le bloc try ligne 710
**Fix**: Ajouté `import sys` dans `fetch_with_smart_limits.py`

### 3. Données trop vieilles
**Problème**: TAIL_BACKFILL_DAYS=1 trop court, créait des trous
**Fix**: Passé à 3 jours dans GitHub Actions

### 4. Buffer trop conservateur  
**Problème**: FRESHNESS_BUFFER_HOURS=2 donnait données de 13h à 15h
**Fix**: Réduit à 1h pour données plus fraîches

## 📊 Architecture Pipeline

```
GitHub Actions (toutes les 2h)
    ↓
fetch_with_smart_limits.py (TAIL_BACKFILL_DAYS=3)
    ↓
baseline_90d_daily.json (380MB)
    ↓
transform_to_columnar.py (ajoute data_min/max_date)
    ↓
data/optimized/*.json (3MB)
    ↓
GitHub Pages → Dashboard
```

## 🔧 Scripts utiles

- **`refresh_local.sh`**: Test complet en local (fetch → transform → copy)
- **`open_dashboard.sh`**: Ouvre dashboard avec bon serveur

## ⚙️ Paramètres clés

- `TAIL_BACKFILL_DAYS=3`: Récupère 3 jours de données (évite les trous)
- `FRESHNESS_BUFFER_HOURS=1`: Données jusqu'à maintenant -1h
- `data_max_date`: Date réelle des données (pas reference_date)

## 🐛 Debug tips

Si date bloquée sur "cargando datos...":
1. Vérifier que `data_max_date` existe dans meta_v1.json
2. Hard refresh navigateur (Cmd+Shift+R)
3. Vérifier console JavaScript pour erreurs

Si pipeline local ne marche pas:
```bash
bash refresh_local.sh
```

## 💾 Stockage persistant

GitHub Releases stocke `baseline_90d_daily.json.zst` (10MB compressé)
- Tag: "baseline"
- Mis à jour toutes les 2h
- Évite perte de données entre runs

## ⚠️ Piège Instagram Carousels (Sept 10, 2025)

**IMPORTANT**: Les carousels Instagram ne sont PAS cassés !
- **Symptôme**: "Cette publication n'est pas disponible" quand on clique
- **Cause**: Instagram requiert d'être connecté pour voir les posts
- **Solution**: Se connecter à Instagram dans le même navigateur
- **NE PAS** perdre de temps à debugger les URLs ou l'API
- Dashboard affiche maintenant un avertissement au premier clic

## 🚀 DÉPLOIEMENT DÉCOUPLÉ (Sept 12, 2025) - 2h de galère

### Le problème initial
- Déployer du code HTML prenait 15 minutes car il relançait le fetch Meta Ads
- Code et données étaient couplés dans un seul workflow
- Création d'un workflow séparé a écrasé les données → dashboard cassé

### La solution (ChatGPT-5)
Deux workflows qui partagent l'artefact Pages :

1. **`🚀 Fast Deploy (Code Only)`** - 36 secondes
   - Récupère l'artefact Pages précédent
   - Remplace SEULEMENT le code
   - Garde les données intactes

2. **`🤖 Auto Refresh Data`** - 15 minutes
   - Fetch Meta Ads + transform
   - Récupère l'artefact Pages précédent  
   - Remplace SEULEMENT les données
   - Garde le code intact

### Chaîne de repli brillante
Le workflow Fast Deploy ne crashe jamais grâce à :
1. Artefact Pages (si existe)
2. Release baseline + transform (reconstruction)
3. JSON vides mais valides (0 ads, pas de crash)
4. Fail seulement si tout échoue

### Leçons apprises
- **L'indentation YAML est CRITIQUE** - step mal indentée = 30 min de debug
- **JSON vides `{}` crashent le dashboard** - toujours des structures valides
- **`concurrency: pages-deploy`** empêche les conflits entre workflows
- **ChatGPT-5 est excellent** pour l'architecture de workflows

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