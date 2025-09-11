# Contexte Complet : Implémentation de graphiques dynamiques basés sur la nomenclature

## 🎯 Objectif Principal
Implémenter 2 graphiques dynamiques dans notre dashboard Meta Ads :
1. **Ángulos Creativos** : Performance par angle marketing
2. **Performance por Creador** : Performance par créateur de contenu

Ces graphiques doivent :
- S'afficher pour TOUT compte utilisant la nomenclature (pas seulement Petcare 2)
- Se mettre à jour quand on change de période (3d, 7d, 14d, etc.)
- Agréger les données en temps réel basé sur le parsing des noms d'annonces

## 📋 Format de Nomenclature
```
Type/Angle/Créateur/Age/Format/Version
Exemple: Nuevo/Picazón/Martin/25-30/IMG/H1
```

## 🔍 Parseurs Existants (on ne sait pas s'ils sont tous utiles)

### 1. scripts/utils/parse_nomenclature.py
**Note : Ce parser n'extrait PAS le champ créateur actuellement**
```python
#!/usr/bin/env python3
"""
Parser pour la nomenclature de Martin
Format détecté : TYPE/ANGLE /FIELD3/ FIELD4/FIELD5/FORMAT /VERSION
"""
import re
from typing import Dict, Optional

def parse_martin_nomenclature(ad_name: str) -> Dict[str, str]:
    """
    Parse le nom d'annonce selon la nomenclature de Martin
    
    Exemple: "Nuevo/Olor a chetos  /NA/ NA/NA/IMG /V3"
    Retourne: {
        'type': 'Nuevo',
        'angle': 'Olor a chetos', 
        'format': 'IMG',
        'version': 'V3',
        'is_nomenclature': True
    }
    """
    
    # Nettoyer le nom
    name = ad_name.strip()
    
    # Vérifier si ça ressemble à la nomenclature de Martin
    if '/' not in name or name.count('/') < 3:
        return {
            'type': 'UNKNOWN',
            'angle': 'UNKNOWN', 
            'format': 'UNKNOWN',
            'version': 'UNKNOWN',
            'is_nomenclature': False,
            'original_name': name
        }
    
    try:
        # Split par /
        parts = [part.strip() for part in name.split('/')]
        
        if len(parts) < 6:  # Au moins TYPE/ANGLE/.../FORMAT/VERSION
            return {
                'type': 'UNKNOWN',
                'angle': 'UNKNOWN', 
                'format': 'UNKNOWN',
                'version': 'UNKNOWN',
                'is_nomenclature': False,
                'original_name': name
            }
        
        # Extraire les parties importantes
        type_creative = parts[0]  # "Nuevo" ou "It"
        angle = parts[1]          # "Olor a chetos", "Problemas digestivos"
        format_part = parts[-2]   # "IMG", "VID", etc.
        version = parts[-1]       # "V1", "V2", "V3"
        
        # Normaliser les valeurs
        if type_creative.lower() in ['it', 'iteracion']:
            type_creative = 'Iteración'
        elif type_creative.lower() in ['nuevo', 'new']:
            type_creative = 'Nuevo'
        
        # Normaliser format
        format_normalized = format_part.upper()
        if format_normalized in ['IMG', 'IMAGE', 'IMAGEN']:
            format_normalized = 'IMAGE'
        elif format_normalized in ['VID', 'VIDEO']:
            format_normalized = 'VIDEO'
        elif format_normalized in ['CAR', 'CAROUSEL', 'CARRUSEL']:
            format_normalized = 'CAROUSEL'
        
        # Normaliser angle (capitaliser première lettre)
        angle_normalized = angle.title() if angle != 'NA' else 'UNKNOWN'
        
        return {
            'type': type_creative,
            'angle': angle_normalized,
            'format': format_normalized, 
            'version': version,
            'is_nomenclature': True,
            'original_name': name,
            'confidence': 'high'
        }
        
    except Exception as e:
        return {
            'type': 'UNKNOWN',
            'angle': 'UNKNOWN', 
            'format': 'UNKNOWN',
            'version': 'UNKNOWN',
            'is_nomenclature': False,
            'original_name': name,
            'error': str(e)
        }
```

### 2. scripts/archive/utils/parser.py
**Note : Parser plus complexe, peut-être pas adapté à notre format actuel**
```python
"""
Module de parsing des noms d'annonces
Extrait angle marketing, créateur et format avec approche multi-niveaux
"""
import re
import json
import logging
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from config import BrandConfig, ParsingConfig

@dataclass
class ParsedEntity:
    """Résultat du parsing d'une annonce"""
    angle: Optional[str] = None
    creator_gender: Optional[str] = None
    creator_age: Optional[int] = None
    format_type: Optional[str] = None
    parse_source: str = "unknown"  # regex, fuzzy, llm, failed
    confidence: float = 0.0
    ambiguity_reason: Optional[str] = None

class AdNameParser:
    """Parse les noms d'annonces avec approche multi-tiers"""
    
    def parse(self, ad_name: str) -> ParsedEntity:
        # Tier 1: Regex strict sur nomenclature officielle
        result = self._parse_regex(ad_name)
        if result.confidence >= 0.9:
            return result
        
        # Tier 2: Fuzzy matching avec dictionnaires
        result = self._parse_fuzzy(ad_name)
        if result.confidence >= 0.7:
            return result
        
        # Tier 3: LLM (si activé)
        if ParsingConfig.ENABLE_LLM:
            result = self._parse_llm(ad_name)
        
        return result
```

## 📊 Structure des Données

### Format des données optimisées (data/optimized/)
```javascript
// agg_v1.json - Données agrégées
{
  "ads": [
    {
      "ad_id": "123456",
      "ad_name": "Nuevo/Picazón/Martin/25-30/IMG/H1",
      "account_name": "Petcare 2",
      "campaign_name": "Campaign ABC",
      "spend": 1000,
      "impressions": 50000,
      "clicks": 500,
      "purchases": 10,
      "purchases_value": 2000,
      
      // Métriques par période
      "period_3d": {
        "spend": 300,
        "impressions": 15000,
        "purchases_value": 600
      },
      "period_7d": {
        "spend": 700,
        "impressions": 35000,
        "purchases_value": 1400
      },
      "period_14d": { /* ... */ },
      "period_30d": { /* ... */ },
      "period_90d": { /* ... */ }
    }
  ]
}

// meta_v1.json - Métadonnées
{
  "accounts": {
    "account_id": {
      "name": "Petcare 2",
      "total_spend": 100000
    }
  },
  "campaigns": { /* ... */ },
  "data_min_date": "2025-09-01",
  "data_max_date": "2025-09-09"
}
```

## 🖥️ Dashboard Actuel (docs/index_full.html)

### Section hardcodée actuelle pour Petcare 2
```html
<!-- SECTION NOMENCLATURA PETCARE -->
<div class="preview-section" id="petcare-section" style="display: none;">
    
    <!-- ÁNGULOS CREATIVOS -->
    <div class="chart-card">
        <h3>📊 Ángulos Creativos - Petcare 2</h3>
        <div class="bar-chart" id="petcare-angles-chart">
            <!-- Barres hardcodées -->
            <div class="bar" style="height: 100%; background: linear-gradient(135deg, #ff9500 0%, #ff950099 100%);">
                <span class="bar-value">$8.8K</span>
                <span class="bar-roas" style="color: #ff9500">1.2 ⚠️</span>
                <span class="bar-label">Picazón</span>
            </div>
            <div class="bar" style="height: 89%;">
                <span class="bar-value">$7.9K</span>
                <span class="bar-label">Olor A Chetos</span>
            </div>
            <!-- ... plus de barres hardcodées ... -->
        </div>
    </div>
    
    <!-- PERFORMANCE POR CREADOR -->
    <div class="chart-card">
        <h3>👥 Performance por Creador</h3>
        <div class="creator-grid" id="petcare-creators-grid">
            <div class="creator-card">
                <div class="creator-avatar female">👩</div>
                <div class="creator-name">Melissa</div>
                <div class="creator-stats">
                    ROAS: <span class="creator-roas">2.1x</span><br>
                    7 ads • $4.2K
                </div>
            </div>
            <!-- ... plus de créateurs hardcodés ... -->
        </div>
    </div>
</div>
```

### Code JavaScript actuel qui affiche/cache la section
```javascript
// Dans updateData()
const petcareSection = document.getElementById('petcare-section');
if (petcareSection) {
    petcareSection.style.display = currentAccountName === 'Petcare 2' ? 'block' : 'none';
}
```

### Variables globales importantes
```javascript
let currentPeriod = '7d';  // Période sélectionnée
let currentAccountName = 'all';  // Compte sélectionné
let currentData = null;  // Données chargées
```

### Fonction existante d'agrégation
```javascript
function aggregateAdsByAdId(ads) {
    const aggregated = {};
    ads.forEach(ad => {
        const id = ad.ad_id;
        if (!aggregated[id]) {
            aggregated[id] = { ...ad };
        } else {
            // Agrège les métriques
            aggregated[id].spend += ad.spend || 0;
            aggregated[id].purchases_value += ad.purchases_value || 0;
            // ...
        }
    });
    return Object.values(aggregated);
}
```

## 🔧 Scripts de Transformation des Données

### scripts/transform_to_columnar.py
**Note : Ce script transforme les données mais ne fait PAS de parsing de nomenclature**
```python
def transform_to_columnar():
    """
    Transforme les données en format columnar optimisé
    """
    # Charge baseline_90d_daily.json
    # Agrège par ad_id et période
    # Génère agg_v1.json, meta_v1.json, etc.
    
    # IMPORTANT: Ce script pourrait être modifié pour pré-calculer
    # les analyses de nomenclature côté serveur
```

## ❓ Questions Critiques

1. **Où implémenter le parsing ?**
   - Côté Python lors de la transformation (pré-calculé) ?
   - Côté JavaScript en temps réel ?
   - Les deux ?

2. **Le champ Créateur manquant**
   - Le parser Python actuel n'extrait PAS le créateur (position [2])
   - Faut-il le corriger côté Python ?
   - Ou seulement l'implémenter en JavaScript ?

3. **Gestion des périodes**
   - Utiliser les fields `period_3d`, `period_7d` déjà agrégés ?
   - Ou recalculer à partir des données de base ?

4. **Performance**
   - Avec 1500+ ads, le parsing JavaScript pourrait être lent
   - Faut-il mettre en cache ?
   - Pré-calculer côté Python ?

5. **Détection automatique de nomenclature**
   - Comment détecter si un compte utilise la nomenclature ?
   - Seuil minimum d'ads avec '/' ?
   - Pattern spécifique ?

## 🎯 Résultat Attendu

```javascript
// Fonction principale à implémenter
function updateNomenclatureCharts(ads, currentPeriod) {
    // 1. Détecter si le compte utilise la nomenclature
    const hasNomenclature = detectNomenclature(ads);
    
    if (!hasNomenclature) {
        hideNomenclatureSection();
        return;
    }
    
    // 2. Parser tous les noms d'ads
    const parsedAds = ads.map(ad => ({
        ...ad,
        parsed: parseNomenclature(ad.ad_name)
    }));
    
    // 3. Analyser par angle
    const angleData = analyzeByAngle(parsedAds, currentPeriod);
    updateAnglesChart(angleData);
    
    // 4. Analyser par créateur
    const creatorData = analyzeByCreator(parsedAds, currentPeriod);
    updateCreatorsChart(creatorData);
    
    showNomenclatureSection();
}
```

## 🤔 Ce que j'attends de toi

Une architecture claire et des recommandations sur :

1. **Architecture globale** : Où placer la logique (Python vs JavaScript) ?
2. **Parser manquant** : Comment gérer l'extraction du créateur ?
3. **Performance** : Comment optimiser pour 1500+ ads ?
4. **Périodes** : Comment utiliser au mieux les données pré-agrégées ?
5. **Code concret** : Les fonctions JavaScript à implémenter

Merci de prendre en compte tous ces éléments pour proposer la meilleure solution !