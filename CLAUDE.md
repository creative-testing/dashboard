# Notes Pipeline Meta Ads - CLAUDE

## ⛔ RÈGLE CRITIQUE: AUCUN DÉPLOIEMENT SANS AUTORISATION EXPLICITE

**IMPORTANT**: Ne JAMAIS faire de push, déploiement, ou modification en production sans l'autorisation explicite de Frederic.

Cela inclut:
- ❌ `git push` vers GitHub (master ou toute branche)
- ❌ Déploiement sur Render ou tout service cloud
- ❌ Déploiement sur GitHub Pages
- ❌ Modifications des GitHub Actions workflows
- ❌ Publication de releases
- ❌ Mise à jour de fichiers en production
- ❌ Lancement manuel de workflows GitHub Actions

**Toujours demander confirmation avant TOUT déploiement.**

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