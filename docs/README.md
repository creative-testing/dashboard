# 🚀 Creative Testing Dashboard

Dashboard d'analyse de performance créative pour Meta Ads optimisé pour Pablo/Martin.

## 📊 Fonctionnalités

### Dashboard Interactif
- **Sélecteur multi-périodes**: 7, 30, 90 jours avec switch instantané
- **KPIs dynamiques**: Annonces actives, investment total, ROAS moyen
- **Analyse par format**: Performance VIDEO vs IMAGE vs INSTAGRAM
- **Comparaison temporelle**: Semaine actuelle vs précédente
- **Links directos**: Accès aux créatifs (vidéos/images)
- **Preview analyses**: Aperçu analyses par angle/createur (post-nomenclature)

### Métriques Avancées
- **📊 Eficiencia por Formato**: Quantité, investment, ROAS, CTR, CPM par format
- **📈 Comparación Semana a Semana**: Évolution des performances
- **🏆 Top 10 ROAS**: Meilleures annonces avec seuil $3K MXN
- **💰 Top Comptes**: Classement par investment

## 🔧 Scripts Production

### `fetch_90d_turbo.py`
Fetch optimisé pour MacBook M1 Pro avec parallélisation aggressive.
- **Performance**: 8,931 annonces/minute  
- **Workers**: 20 en parallèle
- **Pagination**: Complète pour tous les comptes
- **Données**: 90 jours avec time_range précis

### `fetch_hybrid_optimized.py`  
Solution hybride combinant /insights et /ads endpoints.
- **Avantage**: TOUTES les annonces + formats réels quand disponibles
- **Méthode**: Batch API pour rapidité
- **Résultat**: Données complètes sans perte d'annonces

### `fetch_prev_week.py`
Récupération semaine précédente pour comparaisons temporelles.
- **Période**: 12-18 août (7 jours précis)
- **Comparaison**: Équitable avec semaine actuelle (19-25 août)

## 📈 Données Actuelles

### Périodes Disponibles
- **7 jours**: 1,445 annonces, $1.4M MXN
- **30 jours**: 2,453 annonces, $6.5M MXN  
- **90 jours**: 7,561 annonces, $27M MXN (corrigé avec pagination)
- **Semaine précédente**: 1,218 annonces, $1.5M MXN

### Distribution Formats (7j)
- **VIDEO**: 50% (ROAS: 2.85)
- **IMAGE**: 34% (ROAS: 3.24)  
- **INSTAGRAM**: 13% (ROAS: 3.76)
- **OTROS**: 3%

## 🎯 Prochaines Étapes

### Nomenclature Automatisée
- **Formats**: 80% détectés automatiquement via API Meta
- **Creadores**: Mapping nom → âge via dates naissance  
- **Angles**: À fournir par Pablo/Martin
- **Implémentation**: Renommage automatique via API Meta

### Analyses Avancées (Post-Nomenclature)
- Analyse par angle créatif (inflamación, digestión, energía)
- Performance par creador (âge, genre)
- Export Google Sheets automatique
- Actualisation hebdomadaire

## ⚡ Performance Optimisée

**MacBook M1 Pro (10 cores, 64GB):**
- Fetch complet 90j: ~1 minute
- Parallélisation: 20-25 workers
- Batch size: 100 pour rapidité maximale

## 📱 Déploiement

**Netlify**: Dashboard accessible via URL
**Fichiers requis**: 
- `index.html` (dashboard)
- `hybrid_data_*.json` (données périodes)
- `hybrid_data_prev_week.json` (comparaison)

## 🔐 Configuration (Env)

- `FACEBOOK_ACCESS_TOKEN`: token Meta/Facebook avec accès aux comptes nécessaires.

---
*Développé avec Claude Code - Optimisé pour Creative Testing*
