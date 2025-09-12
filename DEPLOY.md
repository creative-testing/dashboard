# 🚀 GUIDE DE DÉPLOIEMENT - SOLUTION FINALE

## ✅ LA SOLUTION QUI MARCHE (Sep 12, 2025)

Après 2h de galère et l'aide de ChatGPT-5, on a ENFIN un système qui marche :

### 🎯 Pour déployer du code (HTML/JS/CSS) :
```bash
git add .
git commit -m "ton message"
git push

# ⏱️ 36 SECONDES et c'est en ligne !
```

### 📊 Pour les données :
- **Automatique** : Toutes les 2h via `🤖 Auto Refresh Data`
- **Manuel** : `gh workflow run refresh-data.yml` (15 min)

## 🏗️ ARCHITECTURE

```
┌─────────────────────────────────────────────────┐
│          🚀 Fast Deploy (Code Only)              │
│              36 secondes                         │
│                                                  │
│  1. Récupère l'artefact Pages précédent         │
│  2. Remplace SEULEMENT le code                  │
│  3. Garde les données intactes                  │
│  4. Déploie                                     │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│         🤖 Auto Refresh Data                     │
│              15 minutes                          │
│                                                  │
│  1. Fetch Meta Ads API                          │
│  2. Transform to optimized format               │
│  3. Récupère l'artefact Pages précédent        │
│  4. Remplace SEULEMENT les données             │
│  5. Garde le code intact                       │
│  6. Déploie                                    │
└─────────────────────────────────────────────────┘
```

## 🛡️ CHAÎNE DE REPLI (Brillante idée de ChatGPT-5)

Le workflow `Fast Deploy` a une chaîne de repli pour ne JAMAIS crasher :

1. **Artefact Pages** → Si existe, utilise les données du dernier déploiement
2. **Release baseline** → Sinon, reconstruit depuis le Release avec `transform_to_columnar.py`
3. **Fallback vide** → Sinon, génère des JSON valides avec 0 ads (pas de crash!)
4. **Fail** → Seulement si tout échoue

## ⚠️ PIÈGES À ÉVITER

### ❌ NE JAMAIS FAIRE :
- Créer un nouveau workflow de déploiement
- Modifier `concurrency: pages-deploy` 
- Toucher aux permissions dans les workflows
- Commiter dans `docs/data/optimized/` (ignoré par Git)
- Imbriquer une step dans le `run:` précédent (indentation YAML!)

### ✅ TOUJOURS FAIRE :
- Vérifier l'indentation YAML (chaque `- name:` au même niveau)
- Utiliser `git push` pour déployer (pas de workflow manuel)
- Attendre 36 secondes pour le code, 15 min pour les données

## 🐛 DEBUGGING

| Problème | Solution |
|----------|----------|
| Dashboard vide/cassé | Attendre le prochain refresh-data (2h) ou lancer manuellement |
| Changements pas visibles | Hard refresh: Cmd+Shift+R |
| Workflow fail immédiat | Erreur YAML! Vérifier l'indentation |
| 404 sur les JSON | Les données ont été écrasées, relancer refresh-data |

## 📁 STRUCTURE DES DONNÉES

```
docs/
├── index_full.html          # Dashboard principal
└── data/
    └── optimized/           # ⚠️ IGNORÉ par Git !
        ├── meta_v1.json     # Généré par GitHub Actions
        ├── agg_v1.json      # Généré par GitHub Actions
        ├── summary_v1.json  # Généré par GitHub Actions
        └── ...              # Généré par GitHub Actions

GitHub Release "baseline"
└── baseline_90d_daily.json.zst  # Backup des données (10MB)
```

## 🎓 LEÇONS APPRISES (Sep 12, 2025)

1. **L'indentation YAML est CRITIQUE** - Une step mal indentée = workflow cassé
2. **Le couplage code/données est mortel** - D'où la séparation en 2 workflows
3. **ChatGPT-5 est brillant** - La chaîne de repli était LA solution
4. **Les JSON vides `{}` cassent tout** - Toujours des structures valides
5. **GitHub Actions cache les artefacts** - On peut les réutiliser entre workflows

## 📚 RÉFÉRENCES

- **`.github/workflows/deploy-fast.yml`** - Déploiement rapide du code
- **`.github/workflows/refresh-data.yml`** - Mise à jour des données
- **`CLAUDE.md`** - Notes sur les problèmes résolus
- **Thread épique** : 2h de debug le Sep 12, 2025

---
*Dernière mise à jour : Sep 12, 2025 - Après la victoire finale*