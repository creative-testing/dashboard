# Contexte : Implémentation de graphiques dynamiques basés sur la nomenclature

## Situation actuelle
Nous avons un dashboard Meta Ads (`docs/index_full.html`) qui affiche des métriques publicitaires. Actuellement, il y a 2 graphiques **hardcodés** pour le compte "Petcare 2" :
1. **Ángulos Creativos** : Montre la performance par angle marketing
2. **Performance por Creador** : Montre la performance par créateur de contenu

Ces graphiques sont statiques dans le HTML et ne répondent pas aux changements de période ou de compte.

## Nomenclature utilisée
Format : `Type/Angle/Créateur/Age/Format/Version`
Exemple : `Nuevo/Picazón/Martin/25-30/IMG/H1`

## Parseurs existants
Nous avons 2 parseurs Python :
1. `scripts/utils/parse_nomenclature.py` - Parse la nomenclature mais **n'extrait PAS le créateur** (field[2])
2. `scripts/archive/utils/parser.py` - Plus complexe mais pas adapté à notre format

## Architecture des données
```
data/optimized/
├── agg_v1.json    # Données agrégées par ad_id et période
├── meta_v1.json   # Métadonnées (comptes, campagnes)
└── summary_v1.json # Statistiques résumées
```

Structure d'un ad dans agg_v1.json :
```json
{
  "ad_id": "123456",
  "ad_name": "Nuevo/Picazón/Martin/25-30/IMG/H1",
  "account_name": "Petcare 2",
  "spend": 1000,
  "purchases_value": 2000,
  "period_3d": { "spend": 300, "purchases_value": 600 },
  "period_7d": { "spend": 700, "purchases_value": 1400 }
}
```

## Objectif
Implémenter ces 2 graphiques de manière **dynamique** pour :
1. Qu'ils s'affichent pour TOUT compte utilisant la nomenclature (pas seulement Petcare 2)
2. Qu'ils se mettent à jour quand on change de période (3d, 7d, 14d, etc.)
3. Qu'ils agrègent les données en temps réel basé sur le parsing des noms

## Approche proposée

### 1. Parser JavaScript dans index_full.html
```javascript
function parseNomenclature(adName) {
    // Parse "Nuevo/Picazón/Martin/25-30/IMG/H1"
    // Retourne: { type, angle, creator, age, format, version, isNomenclature }
}
```

### 2. Fonctions d'analyse
```javascript
function analyzeAngles(ads, period) {
    // Agrège les ads par angle
    // Calcule spend, revenue, ROAS pour chaque angle
    // Retourne tableau trié par spend
}

function analyzeCreators(ads, period) {
    // Agrège les ads par créateur
    // Calcule spend, revenue, ROAS pour chaque créateur
    // Retourne tableau trié par spend
}
```

### 3. Mise à jour des graphiques
```javascript
function updateNomenclatureCharts(ads, currentPeriod) {
    // Vérifie si le compte utilise la nomenclature
    // Si oui, affiche la section et met à jour les graphiques
    // Si non, cache la section
}
```

## Questions clés

1. **Extraction du créateur** : Le parser Python actuel n'extrait pas le créateur (field[2]). Dois-je :
   - Mettre à jour le parser Python pour l'extraire ?
   - Ou juste l'implémenter en JavaScript ?

2. **Gestion des périodes** : Comment récupérer les bonnes métriques selon la période sélectionnée ?
   - Les données ont des fields `period_3d`, `period_7d`, etc.
   - Faut-il utiliser ces fields ou les données de base ?

3. **Détection de nomenclature** : Comment détecter automatiquement si un compte utilise la nomenclature ?
   - Compter les "/" dans les noms ?
   - Vérifier un pattern spécifique ?
   - Avoir une liste de comptes ?

4. **Performance** : Avec 1500+ ads, le parsing en temps réel pourrait être lent. Faut-il :
   - Mettre en cache les résultats parsés ?
   - Pré-calculer côté Python lors de la transformation ?
   - Accepter la latence ?

## Code actuel (hardcodé)
```html
<div id="petcare-section" style="display: none;">
    <div class="bar-chart">
        <!-- Barres hardcodées -->
        <div class="bar" style="height: 100%;">
            <span class="bar-value">$8.8K</span>
            <span class="bar-label">Picazón</span>
        </div>
    </div>
</div>
```

## Ce que j'attends de toi
Une architecture claire pour implémenter ces graphiques dynamiques, en prenant en compte :
- La performance avec beaucoup d'ads
- La réutilisabilité pour d'autres comptes
- La maintenabilité du code
- L'intégration avec l'existant

Quelle est la meilleure approche selon toi ?