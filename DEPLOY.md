# 🚨 GUIDE DE DÉPLOIEMENT - IMPORTANT

## ⚠️ ARCHITECTURE CRITIQUE

Ce projet a **DEUX composants** qui doivent être déployés ensemble :
1. **Le code HTML/JS** (index_full.html)
2. **Les données JSON** (docs/data/optimized/*.json)

## 🔴 PIÈGE MORTEL

**NE JAMAIS créer de workflow "Deploy Pages" séparé !**
- Le workflow `🤖 Auto Refresh Data` gère TOUT le déploiement
- Il récupère les données ET déploie le site
- Un workflow séparé écrasera les données !

## ✅ COMMENT DÉPLOYER

### Pour déployer du code :
```bash
git add .
git commit -m "feat: ..."
git push
# Les changements HTML/JS seront visibles après le prochain run de "Auto Refresh Data" (toutes les 2h)
```

### Pour forcer un déploiement immédiat :
```bash
# Déclenche le workflow complet (15 min)
gh workflow run "🤖 Auto Refresh Data"

# Suivre le statut
gh run list -L 1 --workflow "🤖 Auto Refresh Data"
```

## 📁 STRUCTURE DES DONNÉES

```
docs/
├── index_full.html          # Dashboard
└── data/
    └── optimized/           # ⚠️ IGNORÉ par Git !
        ├── agg_v1.json      # Généré par GitHub Actions
        ├── meta_v1.json     # Généré par GitHub Actions
        └── ...              # Généré par GitHub Actions
```

**IMPORTANT** : Les fichiers dans `docs/data/optimized/` sont :
- ❌ IGNORÉS par Git (.gitignore)
- ✅ Générés automatiquement par GitHub Actions
- ✅ Sauvegardés dans GitHub Releases (baseline)

## 🔄 WORKFLOWS

### 1. `🤖 Auto Refresh Data` (toutes les 2h)
- Récupère les données Meta Ads
- Transforme en format optimisé
- **Déploie TOUT sur GitHub Pages** (code + données)

### 2. `pages-build-deployment` (automatique)
- Déclenché par GitHub après chaque push
- **NE PAS UTILISER** - peut écraser les données

## 🐛 DEBUGGING

### Problème : "404 sur les données JSON"
**Cause** : Un déploiement a écrasé les données
**Solution** :
```bash
gh workflow run "🤖 Auto Refresh Data"
# Attendre 15 min
```

### Problème : "Les changements ne sont pas visibles"
**Causes possibles** :
1. Cache navigateur → Hard refresh (Cmd+Shift+R)
2. Cache CDN GitHub → Attendre 10 min
3. Workflow pas encore passé → Vérifier avec `gh run list`

### Vérifier l'état :
```bash
# Données accessibles ?
curl -I https://fred1433.github.io/creative-testing-dashboard/data/optimized/agg_v1.json

# Dernière version déployée ?
curl -s https://fred1433.github.io/creative-testing-dashboard/index_full.html | grep "Version:"
```

## 🚀 CHECKLIST DE DÉPLOIEMENT

- [ ] Code testé localement (`python -m http.server 8080 --directory docs`)
- [ ] Commit et push
- [ ] Si urgent : `gh workflow run "🤖 Auto Refresh Data"`
- [ ] Attendre 15 min
- [ ] Vérifier sur https://fred1433.github.io/creative-testing-dashboard/index_full.html
- [ ] Hard refresh si nécessaire (Cmd+Shift+R)

## ⏰ TEMPS D'ATTENTE

- Push simple : 2-3h (prochain run automatique)
- Workflow manuel : 15 min
- Changements visibles après déploiement : 1-10 min (cache CDN)

## 💡 RÈGLE D'OR

**Si tu touches JAMAIS aux workflows, souviens-toi :**
> Le workflow `🤖 Auto Refresh Data` doit être le SEUL à déployer sur GitHub Pages !

---
*Dernière mise à jour : Sep 12 2025 - Après 1h de galère*