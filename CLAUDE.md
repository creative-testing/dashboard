# Notes Pipeline Meta Ads - CLAUDE

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